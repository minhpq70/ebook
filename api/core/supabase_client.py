from functools import lru_cache
from supabase import create_client, Client
from .config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Get Supabase client with connection pooling for better performance.
    Connection pooling helps reuse connections and reduce latency.
    """
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_key,
    )
