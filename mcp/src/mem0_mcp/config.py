from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MEM0_API_URL: str = "http://localhost:8000"
    MEM0_API_KEY: str = ""
    MEM0_AGENT_ID: str = ""  # Custom agent ID sent as X-Agent-Id header
    MEM0_USER_ID: str = ""  # Default user ID; overridden by X-User-Id header or per-call param
    MEM0_USER_CACHE_TTL: int = 300  # TTL in seconds for the API-key-to-user-id cache
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8080

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
