import os
import json
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.7-flash"

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".jfif",
    ".webp",
}


# ---------------------------------------------------------
# Gemini Prompt
# ---------------------------------------------------------

def build_prompt(occasion, weather):
    return f"""
You are an expert personal stylist.

The user has provided photographs of their entire wardrobe.

Create the 5 best complete outfits for:

Occasion: {occasion}
Weather: {weather}

IMPORTANT RULES:

1. Carefully examine every clothing image before making
   any recommendation.

2. Use ONLY clothing items that actually appear in the
   provided images.

3. Identify each garment from its image before selecting it.

4. Consider all of the following:
   - garment type
   - color
   - pattern
   - sleeve length
   - overall style
   - formality
   - visual compatibility
   - occasion suitability
   - weather suitability

5. Do NOT recommend garments that are clearly unsuitable
   for the specified weather.

6. Do NOT recommend garments that are clearly unsuitable
   for the specified occasion.

7. Do NOT invent properties that cannot reasonably be
   determined from the image.

   In particular, do NOT claim that an item is:
   - waterproof
   - water-resistant
   - windproof
   - warm
   - breathable
   - lightweight
   - heavy
   - insulated
   - made from a specific material

   unless that information is explicitly provided.

8. Base weather suitability only on what can reasonably
   be inferred from the visible garment itself.

9. Do not create physically invalid outfits.

10. Valid outfit structures include:
    - one top + one bottom
    - one top + one bottom + outerwear/layer
    - one one-piece garment
    - one one-piece garment + outerwear/layer

11. Do NOT combine:
    - two bottoms
    - two unrelated tops
    - multiple garments that cannot logically be worn together

12. Avoid recommending the exact same combination multiple
    times.

13. Make the five recommendations meaningfully different
    where the wardrobe allows it.

14. Rank the outfits from best to worst.

15. Use the EXACT image filename when referring to an item.

16. Every filename in the response MUST correspond to one
    of the provided wardrobe images.

17. Return exactly 5 outfit recommendations if the wardrobe
    contains enough suitable combinations.

18. If fewer than 5 genuinely suitable combinations exist,
    return only the number of genuinely suitable outfits
    rather than inventing poor combinations.

19. Keep each reason short and specific.

Return ONLY valid JSON.

The JSON must have exactly this structure:

{{
  "outfits": [
    {{
      "rank": 1,
      "items": ["filename1.jfif", "filename2.jfif"],
      "reason": "Short explanation of why this outfit works."
    }},
    {{
      "rank": 2,
      "items": ["filename1.jfif", "filename2.jfif"],
      "reason": "Short explanation of why this outfit works."
    }},
    {{
      "rank": 3,
      "items": ["filename1.jfif", "filename2.jfif"],
      "reason": "Short explanation of why this outfit works."
    }},
    {{
      "rank": 4,
      "items": ["filename1.jfif", "filename2.jfif"],
      "reason": "Short explanation of why this outfit works."
    }},
    {{
      "rank": 5,
      "items": ["filename1.jfif", "filename2.jfif"],
      "reason": "Short explanation of why this outfit works."
    }}
  ]
}}
"""


# ---------------------------------------------------------
# Wardrobe Loading
# ---------------------------------------------------------

def get_wardrobe_images(wardrobe_dir):
    wardrobe_dir = Path(wardrobe_dir)

    if not wardrobe_dir.exists():
        raise FileNotFoundError(
            f"Wardrobe directory not found: {wardrobe_dir}"
        )

    if not wardrobe_dir.is_dir():
        raise NotADirectoryError(
            f"Wardrobe path is not a directory: {wardrobe_dir}"
        )

    image_files = sorted(
        path
        for path in wardrobe_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    )

    if not image_files:
        raise RuntimeError(
            f"No supported clothing images found in {wardrobe_dir}"
        )

    return image_files


# ---------------------------------------------------------
# Gemini Recommendation
# ---------------------------------------------------------

def recommend_outfits(wardrobe_dir, occasion, weather):

    image_files = get_wardrobe_images(wardrobe_dir)

    print(f"Found {len(image_files)} wardrobe items.")

    prompt = build_prompt(occasion, weather)

    # First send the instructions.
    contents = [prompt]

    # Then send every wardrobe image together with its filename.
    for image_path in image_files:

        try:
            image = Image.open(image_path)

            # Force the image to RGB so that unusual image
            # formats do not cause problems with the API.
            if image.mode != "RGB":
                image = image.convert("RGB")

        except Exception as error:
            raise RuntimeError(
                f"Could not open wardrobe image: "
                f"{image_path.name}"
            ) from error

        contents.append(
            f"IMAGE FILENAME: {image_path.name}"
        )

        contents.append(image)

    # -----------------------------------------------------
    # Call Gemini with retry handling
    # -----------------------------------------------------

    max_retries = 3
    response = None

    for attempt in range(max_retries):

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
            )

            break

        except Exception as error:

            if attempt == max_retries - 1:
                raise RuntimeError(
                    "Gemini request failed after "
                    f"{max_retries} attempts.\n\n"
                    f"Error: {error}"
                ) from error

            print(
                f"Gemini request failed "
                f"(attempt {attempt + 1}/{max_retries}). "
                f"Retrying in 5 seconds..."
            )

            time.sleep(5)

    # -----------------------------------------------------
    # Process Gemini response
    # -----------------------------------------------------

    if response is None:
        raise RuntimeError(
            "Gemini did not return a response."
        )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    text = response.text.strip()

    # Gemini may occasionally wrap JSON in:
    #
    # ```json
    # {...}
    # ```
    #
    # Remove the code block if present.
    if text.startswith("```"):

        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    try:
        result = json.loads(text)

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Gemini did not return valid JSON.\n\n"
            "Gemini response:\n"
            f"{text}"
        ) from error

    # -----------------------------------------------------
    # Validate top-level response
    # -----------------------------------------------------

    if not isinstance(result, dict):
        raise RuntimeError(
            "Gemini response is not a JSON object."
        )

    if "outfits" not in result:
        raise RuntimeError(
            "Gemini response does not contain 'outfits'."
        )

    outfits = result["outfits"]

    if not isinstance(outfits, list):
        raise RuntimeError(
            "'outfits' must be a list."
        )

    # -----------------------------------------------------
    # Valid wardrobe filenames
    # -----------------------------------------------------

    valid_filenames = {
        path.name
        for path in image_files
    }

    # -----------------------------------------------------
    # Validate every outfit
    # -----------------------------------------------------

    seen_combinations = set()

    for outfit in outfits:

        if not isinstance(outfit, dict):
            raise RuntimeError(
                "Invalid outfit format."
            )

        required_fields = {
            "rank",
            "items",
            "reason",
        }

        if not required_fields.issubset(outfit):
            raise RuntimeError(
                "An outfit is missing one or more required fields."
            )

        # Validate rank
        if not isinstance(outfit["rank"], int):
            raise RuntimeError(
                "Outfit 'rank' must be an integer."
            )

        # Validate items
        if not isinstance(outfit["items"], list):
            raise RuntimeError(
                "Outfit 'items' must be a list."
            )

        if not 1 <= len(outfit["items"]) <= 3:
            raise RuntimeError(
                f"Outfit {outfit['rank']} has an invalid "
                f"number of items: {len(outfit['items'])}"
            )

        # Validate filenames
        for filename in outfit["items"]:

            if not isinstance(filename, str):
                raise RuntimeError(
                    f"Outfit {outfit['rank']} contains "
                    "a non-string filename."
                )

            if filename not in valid_filenames:
                raise RuntimeError(
                    f"Gemini recommended a file that does "
                    f"not exist: {filename}"
                )

        # Make sure the same item isn't repeated within
        # one outfit.
        if len(outfit["items"]) != len(set(outfit["items"])):
            raise RuntimeError(
                f"Outfit {outfit['rank']} contains "
                "the same item more than once."
            )

        # Prevent duplicate outfit combinations.
        combination = tuple(
            sorted(outfit["items"])
        )

        if combination in seen_combinations:
            raise RuntimeError(
                f"Duplicate outfit detected: "
                f"{outfit['items']}"
            )

        seen_combinations.add(combination)

        # Validate reason
        if not isinstance(outfit["reason"], str):
            raise RuntimeError(
                f"Outfit {outfit['rank']} "
                "'reason' must be a string."
            )

    # -----------------------------------------------------
    # Validate ranks
    # -----------------------------------------------------

    ranks = [
        outfit["rank"]
        for outfit in outfits
    ]

    if len(ranks) != len(set(ranks)):
        raise RuntimeError(
            "Duplicate outfit ranks detected."
        )

    # Ranks should start at 1 and be consecutive.
    expected_ranks = list(
        range(1, len(outfits) + 1)
    )

    if sorted(ranks) != expected_ranks:
        raise RuntimeError(
            f"Invalid outfit ranks. "
            f"Expected {expected_ranks}, got {sorted(ranks)}"
        )

    return result


# ---------------------------------------------------------
# Local Test
# ---------------------------------------------------------

if __name__ == "__main__":

    tests = [
        ("College", "Rainy"),
        ("Party", "Normal"),
        ("Office", "Normal"),
        ("Casual", "Hot"),
        ("Formal", "Normal"),
    ]

    for occasion, weather in tests:

        print("\n")
        print("=" * 70)
        print(f"TEST: {occasion} + {weather}")
        print("=" * 70)

        try:

            result = recommend_outfits(
                wardrobe_dir="wardrobe",
                occasion=occasion,
                weather=weather,
            )

            print(
                json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False
                )
            )

        except Exception as error:

            print(
                f"ERROR: {error}"
            )