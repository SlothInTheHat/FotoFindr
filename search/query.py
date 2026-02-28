"""
Parse natural language queries into structured metadata filters.
Simple keyword extraction — no NLP model needed for demo.
"""

import re

EMOTION_WORDS = {
    "happy": ["happy", "smiling", "smile", "laughing", "joyful", "cheerful"],
    "sad": ["sad", "crying", "upset", "unhappy"],
    "angry": ["angry", "mad", "furious", "frustrated"],
    "surprised": ["surprised", "shocked", "amazed"],
    "neutral": ["neutral", "calm", "serious"],
}

_STOPWORDS = {
    "me", "i", "my", "myself", "in", "a", "an", "the", "with", "at", "on",
    "of", "and", "or", "is", "are", "was", "were", "wearing", "holding",
    "looking", "where", "who", "that", "this", "to", "for", "from", "by",
    "photo", "photos", "picture", "pictures", "image", "images", "show",
}


def parse_filters(query: str) -> dict:
    q = query.lower()
    filters: dict = {}

    # --- "me" identity filter ---
    if re.search(r"\bme\b|\bmy\b|\bmyself\b", q):
        filters["wants_me"] = True

    # --- Named person: "of Jake", "with Jake" ---
    name_match = re.search(r"\bof\s+([A-Z][a-z]+)|\bwith\s+([A-Z][a-z]+)", query)
    if name_match:
        filters["person_name"] = name_match.group(1) or name_match.group(2)

    # --- Emotion ---
    for emotion, keywords in EMOTION_WORDS.items():
        if any(kw in q for kw in keywords):
            filters["emotion"] = emotion
            break

    # --- Object keywords (anything not a stopword, length > 2) ---
    words = re.findall(r"\b[a-z]+\b", q)
    obj_keywords = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    if obj_keywords:
        filters["objects"] = obj_keywords

    # --- Low-value filter ---
    if any(kw in q for kw in ["screenshot", "screenshots", "unimportant", "junk", "blurry", "duplicate"]):
        filters["low_value_only"] = True

    return filters
