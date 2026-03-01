import json
import google.generativeai as genai
from backend.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


def find_matching_labels(
    query: str, object_labels: list[str], emotion_labels: list[str]
) -> list[str]:
    """Ask Gemini which object/emotion labels match the user's query.

    Returns a list of matching label strings from the provided sets.
    Falls back to an empty list on any error.
    """
    if not settings.gemini_api_key:
        return []
    if not object_labels and not emotion_labels:
        return []

    prompt = f"""You are a photo search classifier.

User query: "{query}"

Available detected objects: {json.dumps(object_labels)}
Available detected emotions: {json.dumps(emotion_labels)}

Return ONLY a JSON array of items from the above lists that are relevant to the query.
Do not add items that are not in the lists. Do not explain. Just the JSON array.

Example output: ["dog", "happy"]
"""

    try:
        response = _get_model().generate_content(prompt)
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"[gemini] find_matching_labels error: {e}")
        return []


# backend/gemini_service.py

def generate_description(image_bytes, objects, emotions):
    model = _get_model() # Added parens to call the function
    
    prompt = f"""
    You are describing an image for a user.
    Detected objects: {objects}
    Detected emotions: {emotions}

    Using the image and these tags, generate a natural, conversational description.
    Keep it 1-3 sentences.
    """

    # Pass the actual image data as a dict for the GenerativeModel
    response = model.generate_content([
        prompt, 
        {"mime_type": "image/jpeg", "data": image_bytes}
    ])

    return response.text.strip()
