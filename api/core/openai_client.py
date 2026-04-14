from functools import lru_cache
from openai import AsyncOpenAI
from .config import settings


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    """Dùng cho Embedding (Luôn gọi tới OpenAI)"""
    return AsyncOpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def get_chat_openai() -> AsyncOpenAI:
    """Dùng cho Text Generation (Có thể trỏ sang Local LLM như Qwen, Gemma)"""
    kwargs = {
        "api_key": settings.openai_chat_api_key or settings.openai_api_key or "sk-local"
    }
    if settings.openai_chat_base_url:
        kwargs["base_url"] = settings.openai_chat_base_url
    return AsyncOpenAI(**kwargs)
