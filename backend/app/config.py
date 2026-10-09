from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str                      # postgresql+asyncpg://user:pass@host/db?ssl=require
    groq_api_key: str
    admin_token: str = "change-me"         # protects /admin/* routes
    cors_origins: str = "*"                # comma-separated in prod

    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    embed_cache_dir: str = "/tmp/fastembed"

    chat_rate_limit_per_min: int = 20      # per-IP, protects free-tier Groq quota

    # LLM-as-judge. A different model family than the bots under test avoids self-preference bias.
    gemini_api_key: str | None = None
    judge_provider: str = "gemini"         # gemini | groq
    judge_model: str = "gemini-2.5-flash"  # if groq: a non-Llama model, e.g. "openai/gpt-oss-120b"

    eval_concurrency: int = 2              # free-tier rate limits are tight
    latency_budget_ms: int = 4000
    review_sample_pct: int = 10            # random % of results routed to human review


settings = Settings()
