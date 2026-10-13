import os
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")

client = genai.Client(api_key=api_key)

image_path = "wardrobe/top1.jfif"

image = Image.open(image_path)

prompt = """
Look carefully at this clothing item.

Identify:
1. What type of garment it is
2. Main color
3. Pattern
4. Sleeve length
5. Whether it is suitable as a top, bottom, one-piece, or outerwear

Explain your answer briefly. Do not guess if something is genuinely unclear.
"""

response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents=[image, prompt]
)

print("\nGemini's analysis:\n")
print(response.text)