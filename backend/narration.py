# backend/narration.py
import os
import requests
from fastapi import APIRouter, Form
from pathlib import Path
from backend import snowflake_db as sf_db
from backend.gemini_service import generate_description

router = APIRouter()
UPLOAD_DIR = Path("uploads/narrations")
IMAGE_DIR = Path("uploads") # To find the source image

@router.post("/narrate/")
def narrate_photo(device_uri: str = Form(...), user_id: str = Form(...)):
    # 1️⃣ Fetch photo metadata and the UUID (ID) from Snowflake
    with sf_db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT ID, YOLO_DATA, DEEPFACE_DATA FROM PHOTOS WHERE FILENAME = %s",
            (device_uri,)
        )
        row = cur.fetchone()
        if not row:
            return {"error": "Photo record not found in Snowflake"}

        photo_id, yolo_data, deepface_data = row
        objects = [o['label'] for o in yolo_data] if yolo_data else []
        emotions = deepface_data if deepface_data else []

    # 2️⃣ Read the local image file to send to Gemini
    local_image_path = IMAGE_DIR / f"{photo_id}.jpg"
    if not local_image_path.exists():
        return {"error": f"Local image file not found: {photo_id}"}
    
    image_bytes = local_image_path.read_bytes()

    # 3️⃣ Generate description
    description = generate_description(image_bytes, objects, emotions)

    # 4️⃣ Generate audio via ElevenLabs (Corrected URL path)
    voice_id = "EXAVITQu4vr4xnSDxMaL"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    audio_filename = f"{photo_id}_narrate.mp3"
    audio_path = UPLOAD_DIR / audio_filename

    headers = {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY")}
    data = {
        "text": description,
        "model_id": "eleven_multilingual_v2", # v2 is usually better/faster
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }

    r = requests.post(url, headers=headers, json=data)
    if r.status_code != 200:
        return {"error": f"ElevenLabs failed: {r.text}"}

    with open(audio_path, "wb") as f:
        f.write(r.content)

    return {
        "description": description, 
        "audio_url": f"/uploads/narrations/{audio_filename}"
    }