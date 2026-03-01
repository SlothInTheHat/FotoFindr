# backend/narration.py
import os
import requests
from fastapi import APIRouter, Form
from pathlib import Path
from backend import snowflake_db as sf_db
from backend.gemini_service import generate_description

router = APIRouter()

# Directory to store generated audio
UPLOAD_DIR = Path("uploads/narrations")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # You can change to preferred voice


@router.post("/narrate/")
def narrate_photo(device_uri: str = Form(...), user_id: str = Form(...)):
    # 1️⃣ Fetch photo data from Snowflake
    with sf_db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT YOLO_DATA, DEEPFACE_DATA, METADATA FROM PHOTOS WHERE FILENAME = %s",
            (device_uri,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": "Photo not found"}

        yolo_data, deepface_data, metadata = row
        objects = [o["label"] for o in yolo_data] if yolo_data else []
        emotions = deepface_data if deepface_data else []

    # 2️⃣ Generate description via Gemini
    description = generate_description(device_uri, objects, emotions)

    # 3️⃣ Generate audio via ElevenLabs
    audio_path = UPLOAD_DIR / f"{user_id}_{os.path.basename(device_uri)}.mp3"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    data = {
        "voice": ELEVEN_VOICE_ID,
        "model": "eleven_multilingual_v1",
        "text": description,
    }

    r = requests.post(
        "https://api.elevenlabs.io/v1/text-to-speech",
        headers=headers,
        json=data,
        stream=True,
    )
    if r.status_code != 200:
        return {"error": "ElevenLabs TTS failed"}

    with open(audio_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    # 4️⃣ Return audio URL
    return {
        "description": description,
        "audio_url": f"/uploads/narrations/{audio_path.name}",
    }
