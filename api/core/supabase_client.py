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
        options={
            "pool": {
                "min": 2,           # Minimum connections to maintain
                "max": 10,          # Maximum connections allowed
                "idle_timeout": 300,  # Close idle connections after 5 minutes
                "max_lifetime": 3600, # Maximum connection lifetime (1 hour)
                "retry_on_failure": True,  # Retry on connection failures
            }
        }
    )
