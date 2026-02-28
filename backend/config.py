from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str

    # Storage (S3-compatible — DigitalOcean Spaces or AWS S3)
    storage_bucket: str
    storage_endpoint_url: str
    storage_access_key: str
    storage_secret_key: str
    storage_region: str = "nyc3"

    # Database (Snowflake)
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = "FOTOFINDR"
    snowflake_schema: str = "PUBLIC"
    snowflake_warehouse: str = "COMPUTE_WH"

    # Vector DB (pgvector)
    postgres_dsn: str = "postgresql://user:password@localhost:5432/fotofindr"

    # Presage (emotion detection)
    presage_api_key: str = ""
    presage_api_url: str = "https://api.presage.io/v1/emotion"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # default voice

    # App
    max_upload_size_mb: int = 20
    env: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
