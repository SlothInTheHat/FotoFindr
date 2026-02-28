from pydantic_settings import BaseSettings


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

    # App
    max_upload_size_mb: int = 20
    env: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
