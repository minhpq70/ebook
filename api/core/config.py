from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4000

    # Local LLM (Tuỳ chọn cho Qwen, Gemma)
    openai_chat_base_url: str | None = None
    openai_chat_api_key: str | None = None

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str = ""

    # RAG
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 8
    rag_vector_weight: float = 0.7
    rag_fts_weight: float = 0.3

    # App
    app_env: str = "development"
    app_cors_origins: str = "http://localhost:3000"

    # Auth — đặt giá trị ngẫu nhiên mạnh trong .env, KHÔNG commit lên GitHub
    jwt_secret: str = ""
    jwt_expire_hours: int = 24          # token người dùng hết hạn sau 24h
    embed_secret: str = ""              # shared secret với hệ thống NXB
    
    # Google Service Account (cho logging)
    google_sa_json: str = ""            # JSON string hoặc base64 encoded
    
    # Redis (cho caching)
    redis_url: str = "redis://localhost:6379"  # Default Redis URL

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins từ string, validate URLs hợp lệ."""
        origins = [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]
        # Validate basic URL format
        import re
        url_pattern = re.compile(r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?::\d+)?/?$")
        for origin in origins:
            if not url_pattern.match(origin):
                raise ValueError(f"CORS origin không hợp lệ: {origin}")
        return origins

    @model_validator(mode="after")
    def _validate_secrets(self):
        """Fail fast nếu JWT secret chưa được cấu hình đúng."""
        _unsafe = {"", "CHANGE_ME_USE_STRONG_SECRET_IN_DOT_ENV", "CHANGE_ME_EMBED_SECRET"}
        if self.jwt_secret in _unsafe:
            raise ValueError(
                "JWT_SECRET chưa được cấu hình! "
                "Hãy đặt giá trị ngẫu nhiên mạnh trong file .env"
            )
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET phải có ít nhất 32 ký tự")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",")]


settings = Settings()
