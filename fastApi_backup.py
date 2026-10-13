from pathlib import Path
from typing import Optional
import json
import uuid
from datetime import datetime

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from recommender.gemini_recommender import recommend_outfits


# ================================================================
# CONFIG
# ================================================================

BASE_DIR = Path(__file__).resolve().parent

WARDROBE_DIR = BASE_DIR / "wardrobe"
FRONTEND_FILE = BASE_DIR / "frontend.html"

# Persistent application data
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

FAVORITES_FILE = DATA_DIR / "favorites.json"
CALENDAR_FILE = DATA_DIR / "calendar.json"
HISTORY_FILE = DATA_DIR / "history.json"
WARDROBE_METADATA_FILE = DATA_DIR / "wardrobe_metadata.json"


# ================================================================
# APP
# ================================================================

app = FastAPI(
    title="Smart Wardrobe AI API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# MODELS
# ================================================================

class OutfitRequest(BaseModel):
    occasion: str
    temperature_c: float
    rain: bool


# ================================================================
# HELPERS
# ================================================================

def iter_wardrobe_paths():
    """Return all supported wardrobe images."""

    if not WARDROBE_DIR.exists():
        return []

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".jfif",
    }

    return sorted(
        [
            p
            for p in WARDROBE_DIR.iterdir()
            if p.is_file()
            and p.suffix.lower() in extensions
        ],
        key=lambda p: p.name.lower(),
    )


def get_weather_context(
    temperature_c: float,
    rain: bool,
) -> str:
    """Convert frontend weather controls into a context label."""

    if rain:
        return "Rainy"

    if temperature_c >= 30:
        return "Hot"

    if temperature_c >= 20:
        return "Normal"

    if temperature_c >= 10:
        return "Cool"

    return "Cold"


def load_json_file(path: Path, default):
    """
    Load JSON data from disk.

    If the file does not exist or is invalid,
    return the supplied default.
    """

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except (json.JSONDecodeError, OSError):
        return default


def save_json_file(path: Path, data):
    """Save JSON data to disk."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def infer_group(category: str) -> str:
    """Convert a clothing category into a UI group."""

    category = (category or "").strip().lower()

    if category in {
        "dress",
        "one-piece",
    }:
        return "one-piece"

    if category in {
        "bottom",
        "pants",
        "shorts",
        "skirt",
    }:
        return "bottom"

    if category in {
        "outerwear",
        "jacket",
        "shrug",
    }:
        return "outerwear"

    return "top"


def build_wardrobe_item(path: Path):
    """
    Convert a wardrobe image into the structure
    expected by the frontend.

    Gemini performs the actual outfit reasoning.
    Metadata is used for UI/storage only.
    """

    metadata = load_json_file(
        WARDROBE_METADATA_FILE,
        {},
    )

    entry = metadata.get(
        path.name,
        {},
    )

    name = (
        entry.get("name")
        or path.stem
        .replace("_", " ")
        .replace("-", " ")
        .title()
    )

    category = entry.get("category")
    group = entry.get("group")

    # Infer basic values when metadata isn't available.
    if not category:

        lower_name = path.stem.lower()

        if "dress" in lower_name:
            category = "dress"
            group = "one-piece"

        elif any(
            x in lower_name
            for x in [
                "pants",
                "bottom",
                "shorts",
                "skirt",
            ]
        ):
            category = "bottom"
            group = "bottom"

        elif any(
            x in lower_name
            for x in [
                "jacket",
                "shrug",
            ]
        ):
            category = "outerwear"
            group = "outerwear"

        else:
            category = "top"
            group = "top"

    return {
        "id": path.stem,
        "filename": path.name,
        "url": f"/wardrobe/{path.name}",
        "name": name,
        "category": category,
        "group": group or infer_group(category),
        "tags": entry.get("tags", []),
        "confidence": entry.get("confidence"),
        "added_at": entry.get("added_at"),
        "source": entry.get("source", "seed"),
    }


def find_wardrobe_path(item_id: str):
    """Find a wardrobe image by stem or filename."""

    for path in iter_wardrobe_paths():

        if path.stem == item_id:
            return path

        if path.name == item_id:
            return path

    return None


# ================================================================
# BASIC ROUTES
# ================================================================

@app.get("/")
def home():
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return {
        "status": "running",
        "service": "Smart Wardrobe AI API",
        "version": "2.0.0",
    }


@app.get("/app.js")
def get_app_js():
    js_file = BASE_DIR / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/api/status")
def get_status():
    """
    Status endpoint used by the frontend.

    There is no CLIP model or InferenceService.
    Gemini Vision is the recommendation engine.
    """

    wardrobe_count = len(
        iter_wardrobe_paths()
    )

    return {
        "api": "ok",
        "wardrobe_items": wardrobe_count,
        "model_status": {
            "models_loaded": True,
            "can_recommend": True,
            "engine": "Gemini Vision",
            "ranking_mode": "gemini",
            "errors": [],
        },
    }


# ================================================================
# WARDROBE IMAGES
# ================================================================

@app.get("/wardrobe/{filename}")
def get_wardrobe_image(filename: str):
    """Serve a wardrobe image."""

    path = WARDROBE_DIR / filename

    # Prevent path traversal.
    try:

        resolved_path = path.resolve()
        resolved_wardrobe = WARDROBE_DIR.resolve()

        resolved_path.relative_to(
            resolved_wardrobe
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    if (
        not resolved_path.exists()
        or not resolved_path.is_file()
    ):
        raise HTTPException(
            status_code=404,
            detail="Wardrobe item not found",
        )

    return FileResponse(
        resolved_path
    )


# ================================================================
# WARDROBE API
# ================================================================

@app.get("/api/wardrobe")
def get_wardrobe(
    category: Optional[str] = None,
    search: Optional[str] = None,
):

    items = [
        build_wardrobe_item(path)
        for path in iter_wardrobe_paths()
    ]

    if category:

        category_lower = category.lower()

        items = [
            item
            for item in items
            if item["category"].lower()
            == category_lower
        ]

    if search:

        search_lower = search.lower()

        items = [
            item
            for item in items
            if (
                search_lower
                in item["name"].lower()
                or
                search_lower
                in item["filename"].lower()
            )
        ]

    return {
        "count": len(items),
        "items": items,
    }


@app.get("/api/wardrobe/stats")
def wardrobe_stats():

    items = [
        build_wardrobe_item(path)
        for path in iter_wardrobe_paths()
    ]

    favorites = load_json_file(
        FAVORITES_FILE,
        [],
    )

    calendar = load_json_file(
        CALENDAR_FILE,
        {},
    )

    history = load_json_file(
        HISTORY_FILE,
        [],
    )

    return {
        "total": len(items),

        "tops": sum(
            item["group"] == "top"
            for item in items
        ),

        "bottoms": sum(
            item["group"] == "bottom"
            for item in items
        ),

        "outerwear": sum(
            item["group"] == "outerwear"
            for item in items
        ),

        "one_piece": sum(
            item["group"] == "one-piece"
            for item in items
        ),

        "favorites_count": len(
            favorites
        ),

        "planned_outfits": len(
            calendar
        ),

        "worn_outfits": len(
            history
        ),
    }


# ================================================================
# WARDROBE CRUD
# ================================================================

@app.post("/api/wardrobe/items")
async def add_wardrobe_item(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """
    Add a new clothing item.

    No CLIP model is used.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".jfif",
    }

    original_name = Path(
        file.filename
    ).name

    extension = Path(
        original_name
    ).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # Prevent filename collisions.
    base_name = Path(
        original_name
    ).stem

    safe_name = base_name

    existing_names = {
        path.name.lower()
        for path in iter_wardrobe_paths()
    }

    counter = 1

    while (
        f"{safe_name}{extension}".lower()
        in existing_names
    ):

        safe_name = (
            f"{base_name}_{counter}"
        )

        counter += 1

    filename = (
        f"{safe_name}{extension}"
    )

    destination = (
        WARDROBE_DIR / filename
    )

    WARDROBE_DIR.mkdir(
        exist_ok=True
    )

    with open(
        destination,
        "wb",
    ) as f:
        f.write(contents)

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    metadata = load_json_file(
        WARDROBE_METADATA_FILE,
        {},
    )

    item_category = (
        category.strip()
        if category
        else "unclassified"
    )

    item_metadata = {
        "name": (
            name.strip()
            if name
            else Path(filename).stem.title()
        ),

        "category": item_category,

        "group": infer_group(
            item_category
        ),

        "tags": [
            tag.strip()
            for tag in (
                tags or ""
            ).split(",")
            if tag.strip()
        ],

        "confidence": None,

        "added_at": datetime.now().isoformat(),

        "source": "upload",
    }

    metadata[filename] = item_metadata

    save_json_file(
        WARDROBE_METADATA_FILE,
        metadata,
    )

    return {
        "status": "created",
        "item": build_wardrobe_item(
            destination
        ),
    }


@app.patch("/api/wardrobe/items/{item_id}")
async def update_wardrobe_item(
    item_id: str,
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """Update wardrobe item metadata."""

    path = find_wardrobe_path(
        item_id
    )

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="Wardrobe item not found.",
        )

    metadata = load_json_file(
        WARDROBE_METADATA_FILE,
        {},
    )

    entry = metadata.get(
        path.name,
        {},
    )

    if name is not None:
        entry["name"] = name.strip()

    if category is not None:

        category = category.strip()

        entry["category"] = category

        entry["group"] = infer_group(
            category
        )

    if tags is not None:

        entry["tags"] = [
            tag.strip()
            for tag in tags.split(",")
            if tag.strip()
        ]

    metadata[path.name] = entry

    save_json_file(
        WARDROBE_METADATA_FILE,
        metadata,
    )

    return {
        "status": "updated",
        "item": build_wardrobe_item(
            path
        ),
    }


@app.delete("/api/wardrobe/items/{item_id}")
def delete_wardrobe_item(
    item_id: str,
):
    """Delete a wardrobe image and its metadata."""

    path = find_wardrobe_path(
        item_id
    )

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="Wardrobe item not found.",
        )

    try:
        path.unlink()

    except OSError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not delete wardrobe image: "
                f"{exc}"
            ),
        )

    metadata = load_json_file(
        WARDROBE_METADATA_FILE,
        {},
    )

    metadata.pop(
        path.name,
        None,
    )

    save_json_file(
        WARDROBE_METADATA_FILE,
        metadata,
    )

    return {
        "status": "deleted",
        "id": path.stem,
        "filename": path.name,
    }


# ================================================================
# FAVORITES
# ================================================================

@app.get("/api/favorites")
def get_favorites():

    favorites = load_json_file(
        FAVORITES_FILE,
        [],
    )

    return {
        "count": len(favorites),
        "items": favorites,
    }


@app.post("/api/favorites")
def add_favorite(item: dict):

    favorites = load_json_file(
        FAVORITES_FILE,
        [],
    )

    favorite_id = str(
        item.get("id")
        or item.get("item_id")
        or item.get("filename")
        or uuid.uuid4()
    )

    existing = next(
        (
            x
            for x in favorites
            if str(
                x.get("id")
            ) == favorite_id
        ),
        None,
    )

    if existing is not None:

        return {
            "status": "already_exists",
            "item": existing,
        }

    favorite = {
        **item,
        "id": favorite_id,
        "favorited_at": (
            datetime.now().isoformat()
        ),
    }

    favorites.append(
        favorite
    )

    save_json_file(
        FAVORITES_FILE,
        favorites,
    )

    return {
        "status": "created",
        "item": favorite,
    }


@app.delete("/api/favorites/{item_id}")
def delete_favorite(
    item_id: str,
):

    favorites = load_json_file(
        FAVORITES_FILE,
        [],
    )

    new_favorites = [
        item
        for item in favorites
        if str(
            item.get("id")
        ) != item_id
    ]

    if len(new_favorites) == len(
        favorites
    ):
        raise HTTPException(
            status_code=404,
            detail="Favorite not found.",
        )

    save_json_file(
        FAVORITES_FILE,
        new_favorites,
    )

    return {
        "status": "deleted",
        "id": item_id,
    }


# ================================================================
# CALENDAR
# ================================================================

@app.get("/api/calendar")
def get_calendar():

    calendar = load_json_file(
        CALENDAR_FILE,
        {},
    )

    return {
        "items": calendar,
    }


@app.post("/api/calendar")
def add_calendar_event(
    event: dict,
):

    calendar = load_json_file(
        CALENDAR_FILE,
        {},
    )

    key = str(
        event.get("key")
        or event.get("date")
        or uuid.uuid4()
    )

    calendar[key] = {
        **event,
        "key": key,
    }

    save_json_file(
        CALENDAR_FILE,
        calendar,
    )

    return {
        "status": "created",
        "item": calendar[key],
    }


@app.patch("/api/calendar/{key}")
def update_calendar_event(
    key: str,
    event: dict,
):

    calendar = load_json_file(
        CALENDAR_FILE,
        {},
    )

    if key not in calendar:

        raise HTTPException(
            status_code=404,
            detail="Calendar event not found.",
        )

    calendar[key] = {
        **calendar[key],
        **event,
        "key": key,
    }

    save_json_file(
        CALENDAR_FILE,
        calendar,
    )

    return {
        "status": "updated",
        "item": calendar[key],
    }


@app.delete("/api/calendar/{key}")
def delete_calendar_event(
    key: str,
):

    calendar = load_json_file(
        CALENDAR_FILE,
        {},
    )

    if key not in calendar:

        raise HTTPException(
            status_code=404,
            detail="Calendar event not found.",
        )

    del calendar[key]

    save_json_file(
        CALENDAR_FILE,
        calendar,
    )

    return {
        "status": "deleted",
        "key": key,
    }


# ================================================================
# HISTORY
# ================================================================

@app.get("/api/history")
def get_history():

    history = load_json_file(
        HISTORY_FILE,
        [],
    )

    return {
        "count": len(history),
        "items": history,
    }


# ================================================================
# AI OUTFIT GENERATION
# ================================================================

@app.post("/api/outfits/generate")
def generate_outfits(
    request: OutfitRequest,
):

    occasion = (
        request.occasion.strip()
    )

    if not occasion:

        raise HTTPException(
            status_code=400,
            detail="Occasion is required.",
        )

    wardrobe_paths = (
        iter_wardrobe_paths()
    )

    if not wardrobe_paths:

        raise HTTPException(
            status_code=404,
            detail="No wardrobe items found.",
        )

    weather = get_weather_context(
        request.temperature_c,
        request.rain,
    )

    print()
    print("=" * 70)
    print("GEMINI OUTFIT REQUEST")
    print("=" * 70)
    print(
        f"Occasion: {occasion}"
    )
    print(
        f"Temperature: "
        f"{request.temperature_c}°C"
    )
    print(
        f"Rain: {request.rain}"
    )
    print(
        f"Weather context: {weather}"
    )
    print(
        f"Wardrobe items: "
        f"{len(wardrobe_paths)}"
    )

    try:

        results = recommend_outfits(
            wardrobe_dir=WARDROBE_DIR,
            occasion=occasion,
            weather=weather,
        )

    except Exception as exc:

        print(
            "Gemini recommendation error:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Gemini recommendation failed: "
                f"{str(exc)}"
            ),
        )

    # ------------------------------------------------------------
    # Convert Gemini response into frontend format
    # ------------------------------------------------------------

    outfits = []

    for result in results.get(
        "outfits",
        [],
    ):

        item_ids = result.get(
            "items",
            [],
        )

        enriched_items = []

        for filename in item_ids:

            filename = Path(
                str(filename)
            ).name

            matching_path = next(
                (
                    path
                    for path in wardrobe_paths
                    if path.name.lower()
                    == filename.lower()
                ),
                None,
            )

            if matching_path is None:
                continue

            item = build_wardrobe_item(
                matching_path
            )

            enriched_items.append(
                item
            )

        if not enriched_items:
            continue

        outfits.append(
            {
                "rank": result.get(
                    "rank",
                    len(outfits) + 1,
                ),

                "item_ids": [
                    item["id"]
                    for item in enriched_items
                ],

                "items": enriched_items,

                "structure": None,

                "compatibility_score": None,

                "occasion_score": None,

                "weather_score": None,

                "vit_score": None,

                "garment_compatibility_score": None,

                "ranking_mode": "gemini",

                "explanation": result.get(
                    "reason",
                    (
                        "Recommended by Gemini "
                        "based on the selected "
                        "occasion and weather."
                    ),
                ),
            }
        )

    if not outfits:

        raise HTTPException(
            status_code=500,
            detail=(
                "Gemini returned no valid outfits."
            ),
        )

    # ============================================================
    # SAVE GENERATION TO HISTORY
    # ============================================================

    history = load_json_file(
        HISTORY_FILE,
        [],
    )

    history_entry = {
        "id": str(uuid.uuid4()),

        "created_at": (
            datetime.now().isoformat()
        ),

        "occasion": occasion,

        "temperature_c": (
            request.temperature_c
        ),

        "rain": request.rain,

        "weather_context": weather,

        "outfits": outfits,
    }

    history.insert(
        0,
        history_entry,
    )

    # Keep latest 50 generations.
    history = history[:50]

    save_json_file(
        HISTORY_FILE,
        history,
    )

    # ============================================================
    # RESPONSE
    # ============================================================

    return {
        "occasion": occasion,

        "temperature_c": (
            request.temperature_c
        ),

        "rain": request.rain,

        "weather_context": weather,

        "wardrobe_items": (
            len(wardrobe_paths)
        ),

        "ranking_mode": "gemini",

        "outfits": outfits,
    }


# ================================================================
# RUN DIRECTLY
# ================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "fastApi:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )