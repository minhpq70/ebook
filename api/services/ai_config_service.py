"""
AI Config Service
- Load/save cấu hình provider + model từ bảng ai_config trong Supabase
- Bảng giá model (cập nhật thủ công theo tháng)
"""
from core.supabase_client import get_supabase

# ── Danh sách Provider và Model ───────────────────────────────────────────────

AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "chat_models": [
            {"id": "gpt-4o-mini",  "name": "GPT-4o Mini",  "input_price": 0.15,  "output_price": 0.60},
            {"id": "gpt-4o",       "name": "GPT-4o",        "input_price": 2.50,  "output_price": 10.00},
            {"id": "gpt-4-turbo",  "name": "GPT-4 Turbo",   "input_price": 10.00, "output_price": 30.00},
        ],
        "embedding_models": [
            {"id": "text-embedding-3-small", "name": "Embedding 3 Small", "price": 0.02},
            {"id": "text-embedding-3-large", "name": "Embedding 3 Large", "price": 0.13},
        ],
    },
    "google": {
        "name": "Google Gemini",
        "chat_models": [
            {"id": "gemini-1.5-flash",   "name": "Gemini 1.5 Flash",  "input_price": 0.075, "output_price": 0.30},
            {"id": "gemini-1.5-pro",     "name": "Gemini 1.5 Pro",    "input_price": 1.25,  "output_price": 5.00},
            {"id": "gemini-2.0-flash",   "name": "Gemini 2.0 Flash",  "input_price": 0.10,  "output_price": 0.40},
        ],
        "embedding_models": [
            {"id": "text-embedding-004", "name": "Text Embedding 004", "price": 0.00},
        ],
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "chat_models": [
            {"id": "claude-3-haiku-20240307",  "name": "Claude 3 Haiku",       "input_price": 0.25,  "output_price": 1.25},
            {"id": "claude-3-5-sonnet-20241022","name": "Claude 3.5 Sonnet",   "input_price": 3.00,  "output_price": 15.00},
            {"id": "claude-3-opus-20240229",    "name": "Claude 3 Opus",        "input_price": 15.00, "output_price": 75.00},
        ],
        "embedding_models": [],  # Claude không có embedding model riêng
    },
}

# Flat lookup: model_id → giá
_MODEL_PRICE_CACHE: dict[str, dict] = {}
for _prov in AI_PROVIDERS.values():
    for _m in _prov.get("chat_models", []):
        _MODEL_PRICE_CACHE[_m["id"]] = {
            "input":  _m["input_price"],
            "output": _m["output_price"],
        }


def calc_cost(model_id: str, tokens_used: int | None) -> str:
    """Tính chi phí USD ước tính (70% input / 30% output)."""
    if not tokens_used:
        return "n/a"
    price = _MODEL_PRICE_CACHE.get(model_id, {"input": 0.15, "output": 0.60})
    cost = tokens_used * 0.7 * price["input"] / 1_000_000 + \
           tokens_used * 0.3 * price["output"] / 1_000_000
    return f"${cost:.6f}"


# ── Supabase CRUD ─────────────────────────────────────────────────────────────

def get_ai_config() -> dict:
    """Lấy cấu hình AI hiện tại từ Supabase."""
    supabase = get_supabase()
    result = supabase.table("ai_config").select("*").eq("id", 1).execute()
    if result.data:
        return result.data[0]
    return {
        "provider": "openai",
        "chat_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
    }


def update_ai_config(provider: str, chat_model: str, embedding_model: str) -> dict:
    """Cập nhật cấu hình AI và lưu vào Supabase."""
    supabase = get_supabase()
    result = supabase.table("ai_config").upsert({
        "id": 1,
        "provider": provider,
        "chat_model": chat_model,
        "embedding_model": embedding_model,
        "updated_at": "now()",
    }).execute()
    return result.data[0]


def get_current_chat_model() -> str:
    """Lấy tên model chat đang dùng."""
    return get_ai_config().get("chat_model", "gpt-4o-mini")
