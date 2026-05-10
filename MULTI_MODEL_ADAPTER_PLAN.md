# Kế hoạch: Adapter Layer cho Multi-Model RAG Streaming

> **Trạng thái:** Chưa triển khai — Chỉ là tài liệu thiết kế.  
> **Ngày tạo:** 2026-04-22  
> **File liên quan:** `api/services/rag_engine.py`, `api/core/openai_client.py`

---

## 1. Bối cảnh vấn đề

Hệ thống RAG hiện tại (`rag_engine.py`) xử lý streaming output từ LLM, nhưng mỗi model trả dữ liệu theo format khác nhau. Khi chuyển đổi model, code streaming bị "vỡ" vì không nhận diện được output.

### Các model đã test và format output của chúng

| Model | Provider | Thinking/Reasoning | Content (câu trả lời) | Trạng thái |
|---|---|---|---|---|
| **Gemini 2.5 Flash** | Google AI Studio | Không có | `delta.content` chứa text trực tiếp | ✅ Hoạt động tốt |
| **Gemma 4 (27B)** | Google AI Studio | Gói trong tag `<thought>...</thought>` bên trong `delta.content` | Text nằm sau `</thought>` cũng trong `delta.content` | ✅ Đã xử lý (bộ lọc `_strip_thinking`) |
| **Qwen 3.5 (9B)** | Ollama Local (`192.168.50.150:11435`) | Trường riêng `delta.reasoning`, `delta.content` = `""` | `delta.content` chỉ có text thật sau khi reasoning xong | ❌ Bị lỗi "Load failed" |

### Nguyên nhân lỗi với Qwen 3.5

1. Qwen gửi hàng trăm chunk với `delta.content = ""` (chuỗi rỗng) trong khi đang suy luận.
2. Code hiện tại kiểm tra `if delta.content:` → chuỗi rỗng bị bỏ qua → Frontend không nhận được gì.
3. Giai đoạn reasoning kéo dài 10-20 giây → Frontend bị timeout → **"Load failed"**.
4. Phần suy luận nằm ở `delta.reasoning` — một trường mà code hiện tại không đọc.

---

## 2. Giải pháp: Adapter Layer (Lớp chuẩn hóa)

Tạo một hàm/generator trung gian ngồi giữa luồng stream từ LLM và phần gửi SSE cho Frontend.

```
Stream từ LLM  →  [Adapter: chuẩn hóa]  →  SSE cho Frontend
                        ↑
              Nhận diện tự động:
              - Có delta.reasoning?  → Qwen-style thinking
              - Có <thought> tag?   → Gemma-style thinking
              - Chỉ có content?     → Standard (Gemini/GPT)
```

### Yêu cầu thiết kế

- **KHÔNG hiển thị** quá trình thinking/reasoning lên Frontend.
- **KHÔNG cần** cấu hình timeout riêng cho từng model.
- Adapter chỉ cần **lọc bỏ thinking** và **forward content thật**.
- Gửi **heartbeat** (SSE event nhẹ) trong lúc model đang suy luận để giữ kết nối sống.

---

## 3. Thiết kế chi tiết

### 3.1. Hàm Adapter mới (đề xuất)

```python
async def _normalize_stream(raw_stream):
    """
    Generator trung gian: chuẩn hóa output từ mọi model
    về format thống nhất chỉ chứa content thật.
    
    Yields: (content: str | None, usage: Usage | None)
    - content = None nghĩa là chunk này không có text thật (đang thinking)
    - content = str  nghĩa là có text thật để gửi cho frontend
    """
    _in_thinking_tag = False  # cho Gemma-style <thought> tag
    
    async for chunk in raw_stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        usage = chunk.usage
        
        if delta:
            # ── Bước 1: Phát hiện và bỏ qua reasoning (Qwen-style) ──
            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
            if reasoning and not (delta.content and delta.content.strip()):
                # Đang trong giai đoạn thinking, yield None để gửi heartbeat
                yield None, usage
                continue
            
            content = delta.content or ""
            
            # ── Bước 2: Lọc <thought> tag (Gemma-style) ──
            if "<thought>" in content:
                _in_thinking_tag = True
                before = content.split("<thought>")[0]
                if before.strip():
                    yield before, usage
                else:
                    yield None, usage
                continue
            
            if _in_thinking_tag:
                if "</thought>" in content:
                    _in_thinking_tag = False
                    after = content.split("</thought>", 1)[-1]
                    if after.strip():
                        yield after, usage
                    else:
                        yield None, usage
                else:
                    yield None, usage  # Bỏ qua nội dung thinking
                continue
            
            # ── Bước 3: Content thật (Standard) ──
            if content:
                yield content, usage
            else:
                yield None, usage
        
        elif usage:
            yield None, usage
```

### 3.2. Sử dụng trong `stream_rag_query()`

```python
# Thay thế vòng lặp hiện tại:
#   async for chunk in stream:
#       delta = chunk.choices[0].delta ...
#       (logic lọc phức tạp)

# Bằng:
last_heartbeat = time.time()
async for content, usage in _normalize_stream(stream):
    if usage:
        tokens_used = usage.total_tokens
    
    if content:
        full_answer += content
        yield f'data: {json.dumps({"type": "token", "data": content}...)}\n\n'
    else:
        # Gửi heartbeat mỗi 3 giây để giữ kết nối
        now = time.time()
        if now - last_heartbeat > 3:
            yield f'data: {json.dumps({"type": "heartbeat"})}\n\n'
            last_heartbeat = now
```

### 3.3. Frontend (thay đổi tối thiểu)

Frontend chỉ cần thêm **1 dòng** bỏ qua event heartbeat:

```javascript
if (data.type === 'heartbeat') continue;  // Bỏ qua, chỉ giữ kết nối
```

---

## 4. Các model có thể gặp trong tương lai

| Model | Dự đoán format thinking | Adapter xử lý được? |
|---|---|---|
| **DeepSeek R1** | Trường `reasoning_content` riêng | ✅ Đã cover (`getattr` check) |
| **Llama 4** | Không có thinking | ✅ Standard path |
| **Mistral** | Không có thinking | ✅ Standard path |
| **Claude (qua proxy)** | `<thinking>` tag | ⚠️ Cần thêm regex cho tag `<thinking>` |

---

## 5. Checklist triển khai

- [ ] Tạo hàm `_normalize_stream()` trong `rag_engine.py`
- [ ] Refactor `stream_rag_query()` để dùng adapter thay vì logic inline
- [ ] Refactor `run_rag_query()` (blocking) để dùng `_strip_thinking()` mở rộng (xử lý cả reasoning field)
- [ ] Thêm xử lý `heartbeat` event trong Frontend (`test_chat.html` và component Chat chính)
- [ ] Test với Gemini 2.5 Flash (regression)
- [ ] Test với Qwen 3.5 Local
- [ ] Test với Gemma 4 (nếu có)
- [ ] Cập nhật `MODEL_SWITCHING_GUIDE.md` ghi chú rằng adapter đã hỗ trợ mọi model

---

## 6. Ghi chú quan trọng

> **Khi chuyển sang Qwen Local**, ngoài adapter còn cần đảm bảo:
> - File `.env` đã đổi đúng 3 biến (`OPENAI_CHAT_MODEL`, `OPENAI_CHAT_BASE_URL`, `OPENAI_CHAT_API_KEY`)
> - File `openai_client.py` đã có provider `local_proxy` với header `x-api-key` (đã triển khai ngày 2026-04-22)
> - Restart backend: `pm2 restart ebook-api`

> **Hiện tại hệ thống đang chạy Gemini 2.5 Flash** (đã revert về từ Qwen vì lỗi streaming).
