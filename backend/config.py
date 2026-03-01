from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()
import os


class Settings(BaseSettings):
    # Gemini (optional — pipeline only)
    gemini_api_key: str = ""

    # Presage emotion detection (optional)
    presage_api_key: str = ""
    presage_api_url: str = "https://api.presage.io/v1/emotion"

    # Local file storage
    upload_dir: str = "uploads"

    # ElevenLabs (optional)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"

    # Snowflake (optional — mirrors metadata for cloud queries/demo)
    snowflake_account: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
    snowflake_user: str = os.getenv("SNOWFLAKE_USER", "")
    snowflake_password: str = os.getenv("SNOWFLAKE_PASSWORD", "")
    snowflake_database: str = os.getenv("SNOWFLAKE_DATABASE", "")
    snowflake_schema: str = os.getenv("SNOWFLAKE_SCHEMA", "")
    snowflake_warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "")

    # App
    max_upload_size_mb: int = 20
    env: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
