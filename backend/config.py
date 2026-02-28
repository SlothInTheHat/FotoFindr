from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini (required)
    gemini_api_key: str

    # Local file storage (fallback only)
    upload_dir: str = "uploads"

    # S3-compatible object storage (Spaces / R2 / S3)
    storage_backend: str = "local"  # local | s3
    storage_bucket: str = ""
    storage_endpoint_url: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = "us-east-1"
    storage_public_base_url: str = ""
    storage_prefix: str = "uploads"

    # ElevenLabs (optional)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"

    # Presage (emotion API, optional)
    presage_api_key: str = ""
    presage_api_url: str = "https://api.presage.io/v1/emotion"

    # Snowflake
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = "FOTOFINDR"
    snowflake_schema: str = "PUBLIC"
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_role: str = ""

    # App
    max_upload_size_mb: int = 20
    env: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
