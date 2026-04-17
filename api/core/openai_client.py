from functools import lru_cache
import httpx
from openai import AsyncOpenAI
from .config import settings


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    """
    Get OpenAI client for embeddings with optimized connection pooling.
    Uses HTTP/2 and connection reuse for better performance.
    """
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        max_retries=3,
        timeout=httpx.Timeout(60.0, connect=10.0),
        http_client=httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    )


@lru_cache(maxsize=1)
def get_chat_openai() -> AsyncOpenAI:
    """
    Get OpenAI client for chat completion with optimized connection pooling.
    Supports custom base URLs for local LLMs.
    """
    kwargs = {
        "api_key": settings.openai_chat_api_key or settings.openai_api_key or "sk-local",
        "max_retries": 3,
        "timeout": httpx.Timeout(120.0, connect=10.0),  # Longer timeout for chat
        "http_client": httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    }
    if settings.openai_chat_base_url:
        kwargs["base_url"] = settings.openai_chat_base_url
    return AsyncOpenAI(**kwargs)
