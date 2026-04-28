"""
config/settings.py
------------------
Centralised app configuration loaded from .env
"""
import os
from functools import lru_cache
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    # GitHub App
    github_app_id: str = os.getenv("GITHUB_APP_ID", "")
    github_private_key_path: str = os.getenv("GITHUB_PRIVATE_KEY_PATH", "./config/private-key.pem")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

    # NVIDIA NIM
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    nim_structure_model: str = os.getenv("NIM_STRUCTURE_MODEL", "meta/llama3-8b-instruct")
    nim_docs_model: str = os.getenv("NIM_DOCS_MODEL", "meta/llama3-70b-instruct")
    nim_review_model: str = os.getenv("NIM_REVIEW_MODEL", "mistralai/mixtral-8x7b-instruct-v0.1")

    # DB
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./deviq.db")

    # Server
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
