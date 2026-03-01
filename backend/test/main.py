import os
import ast
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Create a Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def find_matches(query: str, objects: list[str], emotions: list[str]) -> list[str]:
    """
    Given a query, list of objects, and list of emotions,
    return only those elements that match the query.
    """
    prompt = f"""
You are a classifier.

User query: "{query}"

Available YOLO objects:
{objects}

Available emotions:
{emotions}

Return ONLY a Python list of elements from the sets that match the query.

Example:
Query: "Pictures of a scared bird"
Objects: ["bird","clock"]
Emotions: ["fear","anger"]
Output:
["bird","fear"]
"""

    # Call the new SDK
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        # You can optionally adjust config (e.g., temperature) here
        config=types.GenerateContentConfig(max_output_tokens=512),
    )

    text = response.text.strip()

    # Safely parse a Python literal (list)
    try:
        matches = ast.literal_eval(text)
        if not isinstance(matches, list) or not all(
            isinstance(x, str) for x in matches
        ):
            matches = []
    except Exception:
        matches = []

    return matches


# Example usage
if __name__ == "__main__":
    objects = ["bird", "clock", "cat"]
    emotions = ["fear", "joy", "anger"]
    print(find_matches("A happy cat on a bird feeder", objects, emotions))
