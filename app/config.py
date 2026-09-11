from pathlib import Path

from pydantic_settings import BaseSettings

# 从 config.py 所在位置推导项目根目录，无论从哪个目录启动都能找到 .env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_clone"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "your-secret-key-change-in-production-abc123xyz"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    tavily_api_key: str = ""
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    chroma_db_path: str = str(_PROJECT_ROOT / "chroma_data")
    use_langchain_agent: bool = False

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
