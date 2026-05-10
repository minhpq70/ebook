"""
AI Config Service
- Đọc cấu hình AI hiện tại trực tiếp từ settings (.env)
- Cập nhật cấu hình bằng cách ghi vào file .env
- Bảng giá model (cập nhật thủ công theo tháng)
"""
from __future__ import annotations

import re
import logging
from pathlib import Path

from core.config import settings

logger = logging.getLogger("ebook.ai_config")

# Đường dẫn tới file .env
_ENV_FILE = Path(__file__).parent.parent / ".env"


# ── Danh sách Provider và Model ───────────────────────────────────────────────

AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": None,  # uses default OpenAI endpoint
        "api_key_env": "OPENAI_API_KEY",
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
    "google_ai_studio": {
        "name": "Google AI Studio (Gemma)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "OPENAI_CHAT_API_KEY",
        "chat_models": [
            {"id": "gemma-4-31b-it",   "name": "Gemma 4 31B IT",   "input_price": 0.00, "output_price": 0.00},
            {"id": "gemma-3-27b-it",   "name": "Gemma 3 27B IT",   "input_price": 0.00, "output_price": 0.00},
            {"id": "gemma-3-12b-it",   "name": "Gemma 3 12B IT",   "input_price": 0.00, "output_price": 0.00},
            {"id": "gemma-3-4b-it",    "name": "Gemma 3 4B IT",    "input_price": 0.00, "output_price": 0.00},
        ],
        "embedding_models": [],  # Dùng embedding của OpenAI
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "OPENAI_CHAT_API_KEY",
        "chat_models": [
            {"id": "gemini-2.5-flash",    "name": "Gemini 2.5 Flash",    "input_price": 0.15, "output_price": 0.60},
            {"id": "gemini-2.5-pro",       "name": "Gemini 2.5 Pro",     "input_price": 1.25, "output_price": 10.00},
            {"id": "gemini-2.0-flash",     "name": "Gemini 2.0 Flash",   "input_price": 0.10, "output_price": 0.40},
        ],
        "embedding_models": [
            {"id": "text-embedding-004", "name": "Text Embedding 004", "price": 0.00},
        ],
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": None,
        "api_key_env": "OPENAI_CHAT_API_KEY",
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_embedding_providers() -> dict:
    """Trả về chỉ các provider có embedding models."""
    return {
        k: v for k, v in AI_PROVIDERS.items()
        if v.get("embedding_models")
    }


def _detect_provider_from_env() -> str:
    """Nhận diện provider đang dùng cho Chat dựa trên cấu hình .env."""
    base_url = settings.openai_chat_base_url or ""
    model = settings.openai_chat_model or ""

    if "192.168" in base_url:
        return "local_proxy"
    if "gemini" in model.lower():
        return "google"
    if "gemma" in model.lower():
        return "google_ai_studio"
    if "generativelanguage.googleapis.com" in base_url:
        return "google_ai_studio"
    return "openai"


# ── Đọc cấu hình AI từ .env (settings) ──────────────────────────────────────

def get_ai_config() -> dict:
    """Lấy cấu hình AI hiện tại trực tiếp từ settings (.env)."""
    provider = _detect_provider_from_env()
    provider_info = AI_PROVIDERS.get(provider, AI_PROVIDERS["openai"])

    return {
        "provider": provider,
        "provider_name": provider_info["name"],
        "chat_model": settings.openai_chat_model,
        "embedding_provider": "openai",
        "embedding_model": settings.openai_embedding_model,
    }


# ── Ghi cấu hình AI vào file .env ────────────────────────────────────────────

def _update_env_var(content: str, key: str, value: str) -> str:
    """Cập nhật hoặc thêm một biến môi trường trong nội dung .env."""
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(f'{key}={value}', content)
    else:
        return content.rstrip() + f'\n{key}={value}\n'


def update_ai_config(
    provider: str,
    chat_model: str,
    embedding_provider: str,
    embedding_model: str,
) -> dict:
    """Cập nhật cấu hình AI bằng cách ghi vào file .env."""
    if not _ENV_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy file .env tại {_ENV_FILE}")

    provider_info = AI_PROVIDERS.get(provider, {})
    base_url = provider_info.get("base_url", "")
    api_key_env = provider_info.get("api_key_env", "OPENAI_CHAT_API_KEY")

    # Đọc nội dung .env hiện tại
    content = _ENV_FILE.read_text(encoding="utf-8")

    # Cập nhật Chat model
    content = _update_env_var(content, "OPENAI_CHAT_MODEL", chat_model)

    # Cập nhật base URL nếu provider có
    if base_url:
        content = _update_env_var(content, "OPENAI_CHAT_BASE_URL", base_url)

    # Cập nhật Embedding model
    content = _update_env_var(content, "OPENAI_EMBEDDING_MODEL", embedding_model)

    # Ghi file
    _ENV_FILE.write_text(content, encoding="utf-8")
    logger.info("Đã cập nhật .env: provider=%s, model=%s, embedding=%s",
                provider, chat_model, embedding_model)

    return {
        "provider": provider,
        "provider_name": provider_info.get("name", provider),
        "chat_model": chat_model,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
    }


def get_current_chat_model() -> str:
    """Lấy tên model chat đang dùng."""
    return settings.openai_chat_model


def get_current_embedding_model() -> str:
    """Lấy tên model embedding đang dùng."""
    return settings.openai_embedding_model
