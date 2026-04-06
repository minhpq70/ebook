from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str = ""

    # RAG
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5
    rag_vector_weight: float = 0.7
    rag_fts_weight: float = 0.3

    # App
    app_env: str = "development"
    app_cors_origins: str = "http://localhost:3000"

    # Auth — đặt giá trị ngẫu nhiên mạnh trong .env, KHÔNG commit lên GitHub
    jwt_secret: str = "CHANGE_ME_USE_STRONG_SECRET_IN_DOT_ENV"
    jwt_expire_hours: int = 24          # token người dùng hết hạn sau 24h
    embed_secret: str = "CHANGE_ME_EMBED_SECRET"  # shared secret với hệ thống NXB

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",")]


settings = Settings()
