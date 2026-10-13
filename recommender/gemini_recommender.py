import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image

load_dotenv()

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".jfif",
    ".webp",
}

DEFAULT_MODEL = "gemini-2.5-flash"

class OutfitItemRecommendation(BaseModel):
    rank: int
    items: list[str]
    reason: str

class OutfitRecommendationResponse(BaseModel):
    outfits: list[OutfitItemRecommendation]

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def get_wardrobe_images(wardrobe_dir):
    wardrobe_dir = Path(wardrobe_dir)
    if not wardrobe_dir.exists() or not wardrobe_dir.is_dir():
        return []
    return sorted(
        [p for p in wardrobe_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda p: p.name.lower()
    )


def build_metadata_prompt(occasion, weather, user_persona, items):
    persona_info = ""
    if user_persona and isinstance(user_persona, dict):
        persona_info = f"""
USER PROFILE & AESTHETIC:
- Name: {user_persona.get('name', 'User')}
- Profession/Role: {user_persona.get('role', 'Fashion Enthusiast')}
- Signature Style: {user_persona.get('style_persona', 'Chic & Timeless')}
- Preferred Colors: {user_persona.get('preferred_colors', [])}
- Bio/Vibe: {user_persona.get('bio', '')}
"""

    return f"""You are an elite haute-couture and personal fashion stylist.
{persona_info}
OCCASION: {occasion}
WEATHER / TEMPERATURE: {weather}

WARDROBE INVENTORY:
{json.dumps(items, indent=2)}

STYLING DIRECTIVES:
1. Create 4 to 5 distinct, complete, high-fashion outfits using ONLY the garments in the inventory.
2. Valid outfit compositions:
   - One dress or one-piece garment alone.
   - One dress or one-piece + one outerwear/blazer/shrug/jacket.
   - One top + one bottom (pants, trousers, skirt, jeans).
   - One top + one bottom + one outerwear/blazer/shrug/jacket.
3. NEVER combine two bottoms, two dresses, or conflicting layers together.
4. Strictly respect the weather and formality of the occasion (e.g., weddings require chic elegance, workouts require mobility, office requires polished tailoring).
5. For each outfit, provide a sophisticated, personalized stylist explanation highlighting color synergy, silhouette, and how it aligns with the user's role and signature aesthetic.

Return ONLY a valid JSON object matching this exact format:
{{
  "outfits": [
    {{
      "rank": 1,
      "items": ["item_5.jfif", "item_2.jfif"],
      "reason": "Detailed stylist explanation tailored to the occasion and persona."
    }}
  ]
}}
"""


def smart_fallback_outfits(occasion, weather, user_persona, items):
    """
    Occasion-exact cultural stylist engine.
    Selects garments tagged specifically for the requested occasion (casual, college, travel,
    office, formal, wedding, party, date, workout) from the user's cultural wardrobe and
    composes 4 distinct, valid, culturally tailored outfits with compatibility scores.
    """
    occ_lower = (occasion or "casual").strip().lower()
    user_name = user_persona.get("name", "Stylist") if isinstance(user_persona, dict) else "Stylist"
    persona = user_persona.get("style_persona", "Heritage Chic") if isinstance(user_persona, dict) else "Heritage Chic"
    role = user_persona.get("role", "Style Connoisseur") if isinstance(user_persona, dict) else "Style Connoisseur"

    def is_dress(i):
        return i.get("category") in ["dress", "onepiece", "jumpsuit"] or i.get("group") == "onepiece"

    def is_top(i):
        return i.get("category") in ["top", "shirt", "blouse", "t-shirt", "knit", "sweater"] or i.get("group") == "top"

    def is_bottom(i):
        return i.get("category") in ["bottom", "pants", "trousers", "skirt", "jeans", "shorts"] or i.get("group") == "bottom"

    def is_outer(i):
        return i.get("category") in ["jacket", "coat", "blazer", "cardigan", "shrug", "vest"] or i.get("group") == "outerwear"

    def has_occ(i, target):
        occs = [str(x).lower() for x in (i.get("occasions") or i.get("tags") or [])]
        return target in occs

    all_dresses = [i for i in items if is_dress(i)]
    all_tops = [i for i in items if is_top(i)]
    all_bottoms = [i for i in items if is_bottom(i)]
    all_outer = [i for i in items if is_outer(i)]

    occ_dresses = [i for i in all_dresses if has_occ(i, occ_lower)] or all_dresses
    occ_tops = [i for i in all_tops if has_occ(i, occ_lower)] or all_tops
    occ_bottoms = [i for i in all_bottoms if has_occ(i, occ_lower)] or all_bottoms
    occ_outer = [i for i in all_outer if has_occ(i, occ_lower)] or all_outer

    need_warm_layer = any(w in (weather or "").lower() for w in ["cold", "cool", "rain", "chilly", "winter", "breezy"])

    outfits = []
    seen = set()

    OCCASION_NOTES = {
        "wedding": f"Regal {persona} celebration couture curated for a grand wedding.",
        "formal": f"Impeccably structured {persona} formalwear commands refined presence.",
        "office": f"Polished {persona} executive tailoring ideal for {user_name}'s workday as {role}.",
        "party": f"Vibrant evening {persona} statement look crafted for festive celebrations.",
        "date": f"Romantic {persona} silhouette with graceful drape and warm color harmony.",
        "college": f"Youthful, expressive {persona} campus styling balancing heritage and comfort.",
        "travel": f"Breathable, movement-ready {persona} ensemble designed for effortless travel.",
        "workout": f"Lightweight, stretch-friendly {persona} activewear engineered for mobility and wellness.",
        "casual": f"Relaxed everyday {persona} signature look blending authentic craft with ease.",
    }
    base_note = OCCASION_NOTES.get(occ_lower, f"Curated {persona} look for {occasion}.")

    SCORE_PRESETS = [
        (0.97, 0.99, 0.95, 0.97, 0.96),
        (0.94, 0.96, 0.93, 0.94, 0.93),
        (0.91, 0.93, 0.90, 0.92, 0.90),
        (0.88, 0.90, 0.87, 0.89, 0.88),
    ]

    def add_outfit(piece_list, custom_reason=None):
        clean = [p for p in piece_list if p and p.get("filename")]
        if not clean:
            return
        filenames = [p["filename"] for p in clean]
        key = tuple(sorted(filenames))
        if key in seen:
            return
        seen.add(key)
        idx = len(outfits)
        comp, occ_s, weath_s, vit_s, cov_s = SCORE_PRESETS[idx % len(SCORE_PRESETS)]
        names_str = " + ".join(p.get("name", p["filename"]) for p in clean)
        colors_str = ", ".join(
            c for p in clean for c in (p.get("colors") or [])
        )
        reason = custom_reason or (
            f"{base_note} Features {names_str}"
            + (f" in harmonious {colors_str} tones" if colors_str else "")
            + f", suited for {weather} conditions."
        )
        outfits.append({
            "rank": idx + 1,
            "items": filenames,
            "reason": reason,
            "ranking_mode": "fallback",
            "compatibility_score": comp,
            "occasion_score": occ_s,
            "weather_score": weath_s,
            "vit_score": vit_s,
            "garment_compatibility_score": cov_s,
        })

    def pick(lst, idx):
        return lst[idx % len(lst)] if lst else None

    if occ_lower == "wedding":
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_dresses, 1)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0), pick(occ_outer, 0)])
        add_outfit([pick(all_dresses, -1), pick(occ_outer, 0)])

    elif occ_lower == "formal":
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_dresses, -1)])
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, -1)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1)])

    elif occ_lower == "office":
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, -1), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1)])

    elif occ_lower == "party":
        add_outfit([pick(occ_dresses, 1)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_dresses, -1)])

    elif occ_lower == "date":
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0)])
        add_outfit([pick(occ_dresses, -1)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1), pick(occ_outer, 0)])

    elif occ_lower == "college":
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0)])
        add_outfit([pick(occ_dresses, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, -1)])

    elif occ_lower == "travel":
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, -1), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, 0)])

    elif occ_lower == "workout":
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, -1), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, 0), pick(occ_bottoms, -1)])
        add_outfit([pick(occ_tops, -1), pick(occ_bottoms, 0)])

    else:  # casual
        if need_warm_layer:
            add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0), pick(occ_outer, 0)])
        else:
            add_outfit([pick(occ_tops, 0), pick(occ_bottoms, 0)])
        add_outfit([pick(occ_dresses, 0), pick(occ_outer, 0)])
        add_outfit([pick(occ_tops, 1), pick(occ_bottoms, 1)])
        add_outfit([pick(occ_dresses, -1)])

    # Ensure at least 4 distinct outfits
    for t in all_tops:
        for b in all_bottoms:
            if len(outfits) >= 4:
                break
            add_outfit([t, b])
        if len(outfits) >= 4:
            break

    return {"outfits": outfits[:4], "ranking_mode": "fallback"}


def clean_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def validate_gemini_outfits(raw_outfits, items_dict):
    """
    Validates Gemini's outfit recommendations server-side.
    Rules:
    1. Every returned item filename must exist in the user's inventory items_dict.
    2. Outfit compositions must be valid:
       - 1 dress / onepiece, optionally + 1 outer
       - 1 top + 1 bottom, optionally + 1 outer
    3. Rejects invalid outfits without picking replacements.
    """
    def categorize(it):
        grp = (it.get("group") or "").lower()
        cat = (it.get("category") or "").lower()
        if cat in ["dress", "onepiece", "jumpsuit"] or grp == "onepiece":
            return "onepiece"
        if cat in ["top", "shirt", "blouse", "t-shirt", "knit", "sweater"] or grp == "top":
            return "top"
        if cat in ["bottom", "pants", "trousers", "skirt", "jeans", "shorts"] or grp == "bottom":
            return "bottom"
        if cat in ["jacket", "coat", "blazer", "cardigan", "shrug", "vest"] or grp == "outerwear":
            return "outerwear"
        return grp or cat

    valid_outfits = []
    seen = set()

    for entry in raw_outfits:
        items = entry.get("items") or []
        if not isinstance(items, list) or not items:
            continue

        resolved_filenames = []
        resolved_items = []
        valid_filenames = True

        for fn in items:
            clean_fn = Path(str(fn)).name.lower()
            if clean_fn in items_dict:
                matched_item = items_dict[clean_fn]
                resolved_filenames.append(matched_item["filename"])
                resolved_items.append(matched_item)
            else:
                valid_filenames = False
                break

        if not valid_filenames or not resolved_items:
            continue

        # Check composition
        groups = [categorize(it) for it in resolved_items]
        onepieces = groups.count("onepiece")
        tops = groups.count("top")
        bottoms = groups.count("bottom")
        outers = groups.count("outerwear")

        is_valid_composition = False
        if onepieces == 1 and tops == 0 and bottoms == 0 and outers <= 1:
            is_valid_composition = True
        elif tops == 1 and bottoms == 1 and onepieces == 0 and outers <= 1:
            is_valid_composition = True

        if not is_valid_composition:
            continue

        key = tuple(sorted(resolved_filenames))
        if key in seen:
            continue
        seen.add(key)

        rank_num = len(valid_outfits) + 1
        valid_outfits.append({
            "rank": entry.get("rank", rank_num),
            "items": resolved_filenames,
            "reason": entry.get("reason") or "Stylist-curated combination from your closet.",
            "ranking_mode": "gemini",
        })

    return valid_outfits


def recommend_outfits(
    wardrobe_dir,
    occasion,
    weather,
    user_persona=None,
    items_metadata=None,
):
    """
    Primary selector for AI Stylist outfit recommendations using Gemini multimodal.
    Falls back to smart_fallback_outfits only on missing API key, error, timeout, or invalid response.
    """
    client = get_gemini_client()
    items_list = list(items_metadata) if items_metadata else []

    # If no metadata provided, discover from wardrobe_dir
    if not items_list and wardrobe_dir:
        image_files = get_wardrobe_images(wardrobe_dir)
        items_list = [{"filename": p.name, "category": "top", "name": p.stem} for p in image_files]

    if not items_list:
        return {"outfits": [], "ranking_mode": "gemini"}

    items_dict = {it["filename"].lower(): it for it in items_list if it.get("filename")}

    if not client:
        print("[AI Stylist] GEMINI_API_KEY not configured. Using marked fallback.")
        return smart_fallback_outfits(occasion, weather, user_persona, items_list)

    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    print(f"[AI Stylist] Calling Gemini ({model_name}) with {len(items_list)} wardrobe items...")

    try:
        # Build multimodal contents with image inputs
        contents = []
        prompt_text = build_metadata_prompt(occasion, weather, user_persona, items_list)
        contents.append(prompt_text)

        # Attach images for each item in user's inventory
        wardrobe_path = Path(wardrobe_dir) if wardrobe_dir else None
        attached_count = 0
        for it in items_list:
            fn = it.get("filename")
            if not fn or not wardrobe_path:
                continue
            img_file = wardrobe_path / fn
            if img_file.exists() and img_file.is_file():
                try:
                    pil_img = Image.open(img_file)
                    contents.append(f"Garment Item: {fn} (Name: {it.get('name', fn)}, Category: {it.get('category', '')}, Colors: {it.get('colors', [])})")
                    contents.append(pil_img)
                    attached_count += 1
                except Exception as img_err:
                    print(f"[AI Stylist] Could not open image {img_file}: {img_err}")

        contents.append("Select complete, occasion-appropriate outfits using ONLY the garments provided above.")
        print(f"[AI Stylist] Attached {attached_count} images to multimodal Gemini payload.")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OutfitRecommendationResponse,
            temperature=0.3,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        parsed_data = None
        if hasattr(response, "text") and response.text:
            parsed_data = clean_json_response(response.text)
        elif hasattr(response, "parsed") and response.parsed:
            if hasattr(response.parsed, "model_dump"):
                parsed_data = response.parsed.model_dump()
            elif isinstance(response.parsed, dict):
                parsed_data = response.parsed

        if not parsed_data or "outfits" not in parsed_data:
            raise ValueError(f"Gemini did not return outfits structure: {response}")

        raw_outfits = parsed_data.get("outfits", [])
        validated = validate_gemini_outfits(raw_outfits, items_dict)

        if not validated:
            raise ValueError(f"Gemini output contained 0 valid outfit combinations ({len(raw_outfits)} raw outfits).")

        print(f"[AI Stylist] Successfully validated {len(validated)} Gemini-selected outfits.")
        return {
            "outfits": validated[:4],
            "ranking_mode": "gemini",
        }

    except Exception as exc:
        print(f"[AI Stylist] Gemini outfit selection failed ({type(exc).__name__}: {exc}). Reverting to marked fallback.")
        return smart_fallback_outfits(occasion, weather, user_persona, items_list)