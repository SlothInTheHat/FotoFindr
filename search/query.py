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


def parse_filters(query: str) -> dict:
    q = query.lower()
    filters: dict = {}

    # --- Person name ---
    # Matches "of Jake", "with Jake", "Jake's"
    name_match = re.search(r"\bof\s+([A-Z][a-z]+)|\bwith\s+([A-Z][a-z]+)", query)
    if name_match:
        filters["person_name"] = name_match.group(1) or name_match.group(2)

    # --- Emotion ---
    for emotion, keywords in EMOTION_WORDS.items():
        if any(kw in q for kw in keywords):
            filters["emotion"] = emotion
            break

    # --- Low-value filter ---
    if any(kw in q for kw in ["screenshot", "screenshots", "unimportant", "junk", "blurry", "duplicate"]):
        filters["low_value_only"] = True
    else:
        filters["exclude_low_value"] = False

    return filters
