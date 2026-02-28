"""
Step 2 (Alternative) — Object detection using YOLO.
Replaces OpenAI Vision for offline/faster inference.
"""

import asyncio
import io
from PIL import Image
from ultralytics import YOLO
from backend.models import DetectedObject

model = YOLO("yolov8n.pt")

def _run_yolo(image_bytes: bytes) -> list[DetectedObject]:

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    results = model(image)
    
    detected_items = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            confidence = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            
            if confidence > 0.3:
                detected_items.append(
                    DetectedObject(label=label.lower(), confidence=confidence)
                )
                
    return detected_items

async def detect_objects(image_bytes: bytes) -> list[DetectedObject]:
    return await asyncio.to_thread(_run_yolo, image_bytes)