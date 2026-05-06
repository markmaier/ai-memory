from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MEM0_API_URL: str = "http://localhost:8000"
    MEM0_API_KEY: str = ""
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8080

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
