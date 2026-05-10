"""
OpenAI Client Factory
- Tạo AsyncOpenAI client cho Chat và Embedding
- Tra bảng provider→credentials từ env vars
- Cache client per provider key để tái sử dụng connections
"""
from __future__ import annotations

import httpx
from openai import AsyncOpenAI

from .config import settings

# ── Provider → Credentials mapping ──────────────────────────────────────────

def _get_provider_credentials(provider: str) -> dict:
    """Tra bảng provider → (api_key, base_url) từ settings."""
    mapping = {
        "openai": {
            "api_key": settings.openai_api_key,
            "base_url": None,  # dùng default OpenAI
        },
        "google_ai_studio": {
            "api_key": (
                settings.google_ai_studio_api_key
                or settings.openai_chat_api_key  # backward compat
                or ""
            ),
            "base_url": settings.google_ai_studio_base_url,
        },
        "google": {
            "api_key": (
                settings.google_ai_studio_api_key
                or settings.openai_chat_api_key
                or ""
            ),
            "base_url": settings.google_ai_studio_base_url,
        },
        "anthropic": {
            "api_key": settings.anthropic_api_key or "",
            "base_url": settings.anthropic_base_url or None,
        },
        "local_proxy": {
            "api_key": settings.openai_chat_api_key or "",
            "base_url": settings.openai_chat_base_url,
            "custom_headers": {"x-api-key": settings.openai_chat_api_key or ""}
        },
    }
    return mapping.get(provider, mapping["openai"])


def get_available_providers() -> dict[str, bool]:
    """Kiểm tra provider nào đã có API key trong env."""
    return {
        "openai": bool(settings.openai_api_key),
        "google_ai_studio": bool(
            settings.google_ai_studio_api_key or settings.openai_chat_api_key
        ),
        "google": bool(
            settings.google_ai_studio_api_key or settings.openai_chat_api_key
        ),
        "anthropic": bool(settings.anthropic_api_key),
    }


# ── Client cache ────────────────────────────────────────────────────────────

_chat_clients: dict[str, AsyncOpenAI] = {}
_embed_clients: dict[str, AsyncOpenAI] = {}


def _make_client(api_key: str, base_url: str | None, timeout: float = 120.0, custom_headers: dict | None = None) -> AsyncOpenAI:
    """Tạo AsyncOpenAI client với connection pooling."""
    kwargs: dict = {
        "api_key": api_key or "sk-placeholder",
        "max_retries": 3,
        "timeout": httpx.Timeout(timeout, connect=10.0),
        "http_client": httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        ),
    }
    if base_url:
        kwargs["base_url"] = base_url
    if custom_headers:
        kwargs["default_headers"] = custom_headers
    return AsyncOpenAI(**kwargs)


# ── Public API ──────────────────────────────────────────────────────────────

def get_chat_openai(provider: str | None = None) -> AsyncOpenAI:
    """
    Lấy AsyncOpenAI client cho Chat/RAG.
    Nếu không truyền provider, dùng provider từ ai_config hoặc fallback env vars.
    """
    if provider is None:
        # Fallback: dùng legacy env vars (backward compat)
        provider = _detect_chat_provider()

    if provider not in _chat_clients:
        creds = _get_provider_credentials(provider)
        _chat_clients[provider] = _make_client(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=120.0,
            custom_headers=creds.get("custom_headers")
        )
    return _chat_clients[provider]


def get_openai(provider: str | None = None) -> AsyncOpenAI:
    """
    Lấy AsyncOpenAI client cho Embedding.
    Nếu không truyền provider, dùng 'openai' (mặc định).
    """
    if provider is None:
        provider = "openai"

    if provider not in _embed_clients:
        creds = _get_provider_credentials(provider)
        _embed_clients[provider] = _make_client(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0,
        )
    return _embed_clients[provider]


def _detect_chat_provider() -> str:
    """
    Phát hiện chat provider từ env vars hiện tại.
    Ưu tiên: local_proxy (nếu base_url là IP LAN) → google_ai_studio → openai.
    """
    if settings.openai_chat_base_url and "192.168" in settings.openai_chat_base_url:
        return "local_proxy"
    if settings.google_ai_studio_api_key or settings.openai_chat_api_key:
        return "google_ai_studio"
    return "openai"
