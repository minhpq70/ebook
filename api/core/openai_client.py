from functools import lru_cache
from openai import AsyncOpenAI
from .config import settings


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)
