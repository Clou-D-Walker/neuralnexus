"""
security/settings.py
--------------------
Application-level configuration loaded from a .env file via Pydantic.

Required .env keys:
  AES_SECRET  – Secret key used for AES-256 session token encryption.
  NODE_ID     – Unique UUID identifying this Raft node.
"""

from pydantic_settings import BaseSettings
import os


_env_file = os.environ.get("ENV_FILE", ".env")


class Settings(BaseSettings):
    AES_SECRET: str
    NODE_ID: str

    model_config = {"env_file": _env_file}


settings = Settings()
