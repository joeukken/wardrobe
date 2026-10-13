from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import uuid
import sqlite3
import hashlib
import shutil
from datetime import datetime

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
    Header,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from recommender.gemini_recommender import recommend_outfits
from database import DB_PATH, get_db, init_database, seed_users_and_wardrobes, hash_password, SEED_ITEMS_METADATA

# ================================================================
# CONFIG
# ================================================================

BASE_DIR = Path(__file__).resolve().parent
WARDROBE_DIR = BASE_DIR / "wardrobe"
USERS_WARDROBES_DIR = BASE_DIR / "user_wardrobes"
USERS_WARDROBES_DIR.mkdir(exist_ok=True)
FRONTEND_FILE = BASE_DIR / "frontend.html"

# Run database setup on startup
init_database()
seed_users_and_wardrobes()

# ================================================================
# APP
# ================================================================

app = FastAPI(
    title="Smart Wardrobe AI API - Multi-User Edition",
    version="3.0.0",
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

class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    name: Optional[str] = ""
    username: Optional[str] = ""
    password: str
    style_persona: Optional[str] = "Personal & Chic"
    role: Optional[str] = "Member"
    bio: Optional[str] = None

class OutfitRequest(BaseModel):
    occasion: str
    temperature_c: float
    rain: bool

class CalendarEventRequest(BaseModel):
    key: Optional[str] = None
    date: str
    occasion: str
    weather: Optional[str] = None
    outfit: Optional[dict] = None
    worn: Optional[bool] = False
    rating: Optional[int] = 5

class FavoriteRequest(BaseModel):
    id: Optional[str] = None
    item_id: Optional[str] = None
    filename: Optional[str] = None
    occasion: Optional[str] = None
    items: Optional[List[dict]] = None
    reason: Optional[str] = None
    explanation: Optional[str] = None
    score: Optional[float] = None

# ================================================================
# AUTH & USER CONTEXT
# ================================================================

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Extract authenticated user from Authorization header (Bearer username or Bearer user_id).
    Defaults to the first seeded user (emma_casual) if no auth header is supplied.
    """
    conn = get_db()
    cursor = conn.cursor()
    user_id = None
    username = None

    if authorization and authorization.strip():
        parts = authorization.strip().split()
        token = parts[1] if len(parts) > 1 else parts[0]
        token = token.strip()
        if token.isdigit():
            user_id = int(token)
        else:
            username = token

    if user_id is not None:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif username:
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    else:
        cursor.execute("SELECT * FROM users ORDER BY id ASC LIMIT 1")

    row = cursor.fetchone()
    conn.close()

    if not row:
        # Fallback to first user
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="No users found in database.")

    user = dict(row)
    if isinstance(user.get("preferred_colors"), str):
        try:
            user["preferred_colors"] = json.loads(user["preferred_colors"])
        except Exception:
            pass
    return user

def get_user_wardrobe_dir(user_id: int) -> Path:
    user_dir = USERS_WARDROBES_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def infer_group(category: str) -> str:
    category = (category or "").strip().lower()
    if category in {"dress", "one-piece"}:
        return "one-piece"
    if category in {"bottom", "pants", "shorts", "skirt"}:
        return "bottom"
    if category in {"outerwear", "jacket", "shrug"}:
        return "outerwear"
    return "top"

def get_weather_context(temperature_c: float, rain: bool) -> str:
    if rain:
        return "Rainy"
    if temperature_c >= 30:
        return "Hot"
    if temperature_c >= 20:
        return "Normal"
    if temperature_c >= 10:
        return "Cool"
    return "Cold"

# ================================================================
# BASIC & AUTH ROUTES
# ================================================================

@app.get("/")
def home():
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {
        "status": "running",
        "service": "Smart Wardrobe AI API - Multi-User",
        "version": "3.0.0",
    }

@app.get("/app.js")
def get_app_js():
    js_file = BASE_DIR / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/api/auth/users")
def get_available_users():
    """Returns all 20 registered personas for easy multi-account switching and login."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.name, u.role, u.style_persona, u.preferred_colors, u.temp_pref, u.bio,
               COUNT(w.id) as wardrobe_count
        FROM users u
        LEFT JOIN wardrobe_items w ON u.id = w.user_id
        GROUP BY u.id
        ORDER BY u.id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    users = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("preferred_colors"), str):
            try:
                d["preferred_colors"] = json.loads(d["preferred_colors"])
            except Exception:
                pass
        users.append(d)
    return {"count": len(users), "users": users}

@app.post("/api/auth/login")
def login(creds: LoginRequest):
    """Authenticate a user account. Accepts username or original name. Default password for seeded accounts is 'pass123'."""
    conn = get_db()
    cursor = conn.cursor()
    pwd_hash = hash_password(creds.password)
    identifier = creds.username.strip().lower()

    cursor.execute("""
        SELECT * FROM users 
        WHERE (
            LOWER(username) = ? 
            OR LOWER(name) = ? 
            OR REPLACE(LOWER(name), ' ', '_') = ? 
            OR REPLACE(LOWER(name), ' ', '') = ?
            OR LOWER(username) LIKE ?
            OR LOWER(name) LIKE ?
        )
        AND password_hash = ?
    """, (identifier, identifier, identifier, identifier, f"{identifier}%", f"{identifier}%", pwd_hash))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user = dict(row)
    user.pop("password_hash", None)
    if isinstance(user.get("preferred_colors"), str):
        try:
            user["preferred_colors"] = json.loads(user["preferred_colors"])
        except Exception:
            pass

    return {
        "status": "success",
        "token": str(user["id"]),
        "user": user,
    }

@app.post("/api/auth/signup")
def signup(payload: SignupRequest):
    """Register a new user account and provision their full 20-piece occasion-tagged wardrobe."""
    raw_username = (payload.username or "").strip().lower()
    raw_name = (payload.name or "").strip()
    password = (payload.password or "").strip()

    if not raw_name and raw_username:
        raw_name = raw_username.replace("_", " ").replace(".", " ").replace("-", " ").title()
    if not raw_username and raw_name:
        import re
        raw_username = re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_")

    username = raw_username
    name = raw_name
    style_persona = (payload.style_persona or "Personal & Chic").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    conn = get_db()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    cursor.execute("SELECT id FROM users WHERE LOWER(username) = ?", (username,))
    existing = cursor.fetchone()
    user_id = None

    if existing:
        existing_id = existing["id"]
        if existing_id > 20:
            # Reuse and update the user's previously created custom account
            user_id = existing_id
            cursor.execute("""
                UPDATE users SET password_hash = ?, name = ? WHERE id = ?
            """, (pwd_hash, name, user_id))
            conn.commit()
        else:
            # Avoid colliding with the 20 seeded cultural accounts by assigning a unique username
            suffix = 2
            while True:
                candidate = f"{username}_{suffix}"
                cursor.execute("SELECT id FROM users WHERE LOWER(username) = ?", (candidate,))
                if not cursor.fetchone():
                    username = candidate
                    break
                suffix += 1

    if user_id is None:
        default_colors = json.dumps(["Black", "White", "Navy", "Beige"])
        bio = payload.bio or f"Personal curated wardrobe for {name}."
        cursor.execute("""
            INSERT INTO users (username, password_hash, name, role, style_persona, preferred_colors, temp_pref, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            pwd_hash,
            name,
            payload.role or "Member",
            style_persona,
            default_colors,
            "Balanced",
            bio
        ))
        user_id = cursor.lastrowid
        conn.commit()

    # Create empty wardrobe directory for the new user (no pre-seeded items)
    user_dir = USERS_WARDROBES_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    for f in user_dir.iterdir():
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass
    cursor.execute("DELETE FROM wardrobe_items WHERE user_id = ?", (user_id,))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    user = dict(row)
    user.pop("password_hash", None)
    if isinstance(user.get("preferred_colors"), str):
        try:
            user["preferred_colors"] = json.loads(user["preferred_colors"])
        except Exception:
            pass

    return {
        "status": "success",
        "message": "Account created successfully",
        "token": str(user["id"]),
        "user": user,
    }

@app.get("/api/auth/me")
def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    clean_user = dict(current_user)
    clean_user.pop("password_hash", None)
    return clean_user

@app.get("/api/status")
def get_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM wardrobe_items WHERE user_id = ?", (user_id,))
    wardrobe_count = cursor.fetchone()["cnt"]
    conn.close()

    return {
        "api": "ok",
        "current_user": {
            "id": current_user["id"],
            "username": current_user["username"],
            "name": current_user["name"],
            "style_persona": current_user["style_persona"],
        },
        "wardrobe_items": wardrobe_count,
        "model_status": {
            "models_loaded": True,
            "can_recommend": True,
            "engine": "Gemini Vision (Multi-User)",
            "ranking_mode": "gemini",
            "errors": [],
        },
    }

# ================================================================
# WARDROBE IMAGES & STATIC FILES
# ================================================================

@app.get("/wardrobe/{filename}")
def get_wardrobe_image_generic(filename: str):
    """Fallback to serve seed images or global images."""
    no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    path = WARDROBE_DIR / filename
    if path.exists() and path.is_file():
        return FileResponse(path, headers=no_cache)
    # Check if found in any user directory
    for udir in USERS_WARDROBES_DIR.iterdir():
        if udir.is_dir() and (udir / filename).exists():
            return FileResponse(udir / filename, headers=no_cache)
    raise HTTPException(status_code=404, detail="Wardrobe item not found")

@app.get("/wardrobe/{user_id}/{filename}")
def get_user_wardrobe_image(user_id: int, filename: str):
    no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    user_dir = USERS_WARDROBES_DIR / str(user_id)
    path = user_dir / filename
    if path.exists() and path.is_file():
        return FileResponse(path, headers=no_cache)
    # Fallback to seed directory
    seed_path = WARDROBE_DIR / filename
    if seed_path.exists() and seed_path.is_file():
        return FileResponse(seed_path, headers=no_cache)
    raise HTTPException(status_code=404, detail="Wardrobe item not found")

# ================================================================
# WARDROBE API
# ================================================================

VALID_OCCASIONS = {"casual", "college", "travel", "office", "formal", "wedding", "party", "date", "workout"}

def infer_item_occasions(name: str, category: str, tags: list) -> list:
    explicit = [t.lower() for t in tags if t.lower() in VALID_OCCASIONS]
    if explicit:
        return explicit
    name_l = name.lower()
    inferred = set()
    if any(k in name_l for k in ["wedding", "anarkali", "kasavu", "zari", "brocade", "gala", "velvet", "gown"]):
        inferred.update(["wedding", "formal", "party"])
    if any(k in name_l for k in ["blazer", "trousers", "slacks", "formal", "office", "poplin", "shirt", "suit"]):
        inferred.update(["office", "formal"])
    if any(k in name_l for k in ["breezy", "travel", "linen", "culotte", "shrug", "resort", "chinos"]):
        inferred.update(["travel", "casual"])
    if any(k in name_l for k in ["kurti", "cotton", "denim", "skirt", "tee", "smock"]):
        inferred.update(["college", "casual"])
    if any(k in name_l for k in ["slip", "cocktail", "silk", "satin"]):
        inferred.update(["party", "date"])
    if any(k in name_l for k in ["relax", "salwar", "dhoti", "drawstring"]):
        inferred.update(["casual", "workout"])
    return sorted(list(inferred)) if inferred else ["casual", "college"]

def format_db_item(row: dict) -> dict:
    stem = Path(row["filename"]).stem
    user_id = row["user_id"]
    tags_list = []
    if row.get("tags"):
        try:
            tags_list = json.loads(row["tags"]) if row["tags"].startswith("[") else [t.strip() for t in row["tags"].split(",") if t.strip()]
        except Exception:
            tags_list = []
    colors_list = []
    if row.get("colors"):
        try:
            colors_list = json.loads(row["colors"]) if row["colors"].startswith("[") else [c.strip() for c in row["colors"].split(",") if c.strip()]
        except Exception:
            colors_list = []

    occasions = infer_item_occasions(row["name"], row["category"], tags_list)

    return {
        "id": stem,
        "filename": row["filename"],
        "url": f"/wardrobe/{user_id}/{row['filename']}",
        "name": row["name"],
        "category": row["category"],
        "group": row["group_type"],
        "style": row.get("style", "casual"),
        "colors": colors_list,
        "warmth": row.get("warmth_level", 2),
        "tags": tags_list,
        "occasions": occasions,
        "is_favorite": bool(row.get("is_favorite", 0)),
        "added_at": row.get("added_at") or "",
        "source": "closet",
    }

@app.get("/api/wardrobe")
def get_wardrobe(
    category: Optional[str] = None,
    occasion: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wardrobe_items WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    items = [format_db_item(dict(r)) for r in rows]

    if category and category.lower() != "all":
        cat_lower = category.lower()
        items = [it for it in items if it["category"].lower() == cat_lower or it["group"].lower() == cat_lower]

    if occasion and occasion.lower() != "all":
        occ_lower = occasion.lower()
        items = [it for it in items if occ_lower in [o.lower() for o in it.get("occasions", [])]]

    if search:
        s_lower = search.lower()
        items = [it for it in items if s_lower in it["name"].lower() or s_lower in it["filename"].lower() or any(s_lower in o for o in it.get("occasions", []))]

    return {"count": len(items), "items": items}

@app.get("/api/wardrobe/stats")
def wardrobe_stats(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wardrobe_items WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    items = [format_db_item(r) for r in rows]

    cursor.execute("SELECT COUNT(*) as cnt FROM favorites WHERE user_id = ?", (user_id,))
    fav_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM planned_outfits WHERE user_id = ?", (user_id,))
    planned_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM planned_outfits WHERE user_id = ? AND worn = 1", (user_id,))
    worn_count = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "total": len(items),
        "tops": sum(it["group"] == "top" for it in items),
        "bottoms": sum(it["group"] == "bottom" for it in items),
        "outerwear": sum(it["group"] == "outerwear" for it in items),
        "one_piece": sum(it["group"] == "one-piece" for it in items),
        "favorites_count": fav_count,
        "planned_outfits": planned_count,
        "worn_outfits": worn_count,
        "recent_items": items[:4],
        "user": {
            "name": current_user["name"],
            "style": current_user["style_persona"],
            "role": current_user["role"],
        }
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
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    user_dir = get_user_wardrobe_dir(user_id)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    allowed = {".jpg", ".jpeg", ".png", ".webp", ".jfif"}
    orig_name = Path(file.filename).name
    ext = Path(orig_name).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported image format.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    base_name = Path(orig_name).stem
    safe_name = base_name
    counter = 1
    while (user_dir / f"{safe_name}{ext}").exists():
        safe_name = f"{base_name}_{counter}"
        counter += 1

    filename = f"{safe_name}{ext}"
    dest = user_dir / filename
    with open(dest, "wb") as f:
        f.write(contents)

    item_cat = (category.strip() if category else "top").lower()
    item_group = infer_group(item_cat)
    item_name = name.strip() if name else safe_name.replace("_", " ").title()

    tags_list = [t.strip() for t in (tags or "").split(",") if t.strip()]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wardrobe_items (user_id, filename, name, category, group_type, style, tags, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        filename,
        item_name,
        item_cat,
        item_group,
        current_user.get("style_persona", "casual"),
        json.dumps(tags_list),
        datetime.now().isoformat()
    ))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM wardrobe_items WHERE id = ?", (new_id,))
    row = dict(cursor.fetchone())
    conn.close()

    invalidate_user_recommendation_cache(user_id)
    return {"status": "created", "item": format_db_item(row)}

@app.patch("/api/wardrobe/items/{item_id}")
async def update_wardrobe_item(
    item_id: str,
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wardrobe_items WHERE user_id = ? AND (filename LIKE ? OR filename = ?)",
                   (user_id, f"{item_id}.%", item_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Wardrobe item not found.")

    item_row = dict(row)
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if category is not None:
        cat_clean = category.strip().lower()
        updates.append("category = ?")
        params.append(cat_clean)
        updates.append("group_type = ?")
        params.append(infer_group(cat_clean))
    if tags is not None:
        t_list = [t.strip() for t in tags.split(",") if t.strip()]
        updates.append("tags = ?")
        params.append(json.dumps(t_list))

    if updates:
        params.append(item_row["id"])
        cursor.execute(f"UPDATE wardrobe_items SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    cursor.execute("SELECT * FROM wardrobe_items WHERE id = ?", (item_row["id"],))
    updated_row = dict(cursor.fetchone())
    conn.close()

    invalidate_user_recommendation_cache(user_id)
    return {"status": "updated", "item": format_db_item(updated_row)}

@app.delete("/api/wardrobe/items/{item_id}")
def delete_wardrobe_item(item_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    user_dir = get_user_wardrobe_dir(user_id)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wardrobe_items WHERE user_id = ? AND (filename LIKE ? OR filename = ?)",
                   (user_id, f"{item_id}.%", item_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Wardrobe item not found.")

    item_row = dict(row)
    cursor.execute("DELETE FROM wardrobe_items WHERE id = ?", (item_row["id"],))
    conn.commit()
    conn.close()

    file_path = user_dir / item_row["filename"]
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass

    invalidate_user_recommendation_cache(user_id)
    return {"status": "deleted", "id": item_id, "filename": item_row["filename"]}

# ================================================================
# FAVORITES API
# ================================================================

@app.get("/api/favorites")
def get_favorites(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favorites WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    favorites = []
    for r in rows:
        try:
            item_data = json.loads(r["item_data_json"])
            item_data["id"] = r["fav_key"]
            favorites.append(item_data)
        except Exception:
            pass
    return {"count": len(favorites), "items": favorites}

@app.post("/api/favorites")
def add_favorite(item: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    fav_key = str(item.get("id") or item.get("item_id") or item.get("filename") or uuid.uuid4())

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favorites WHERE user_id = ? AND fav_key = ?", (user_id, fav_key))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return {"status": "already_exists", "item": json.loads(existing["item_data_json"])}

    favorite_obj = {**item, "id": fav_key, "favorited_at": datetime.now().isoformat()}

    cursor.execute("""
        INSERT INTO favorites (user_id, fav_key, item_data_json)
        VALUES (?, ?, ?)
    """, (user_id, fav_key, json.dumps(favorite_obj)))
    conn.commit()
    conn.close()

    return {"status": "created", "item": favorite_obj}

@app.delete("/api/favorites/{item_id}")
def delete_favorite(item_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorites WHERE user_id = ? AND fav_key = ?", (user_id, item_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail="Favorite not found.")
    return {"status": "deleted", "id": item_id}

# ================================================================
# CALENDAR API
# ================================================================

@app.get("/api/calendar")
def get_calendar(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM planned_outfits WHERE user_id = ? ORDER BY date ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    events = {}
    for r in rows:
        d = dict(r)
        items_data = []
        try:
            items_data = json.loads(d["items_json"])
        except Exception:
            pass
        event_dict = {
            "key": d["date"],
            "date": d["date"],
            "occasion": d["occasion"],
            "outfit_title": d.get("outfit_title") or f"{(d.get('occasion') or 'Planned').title()} Look",
            "weather": d.get("weather") or "Normal",
            "reason": d.get("reason") or "",
            "worn": bool(d.get("worn", 0)),
            "rating": d.get("rating", 5),
            "items": items_data,
            "item_ids": [it.get("id") for it in items_data if isinstance(it, dict) and it.get("id")],
            "outfit": {
                "items": items_data,
                "reason": d.get("reason") or "",
            }
        }
        events[d["date"]] = event_dict

    return {"items": events}

@app.post("/api/calendar")
def add_calendar_event(event: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    date_key = str(event.get("key") or event.get("date") or datetime.now().strftime("%Y-%m-%d"))
    occasion = event.get("occasion", "casual")
    weather = event.get("weather", "Normal")
    worn = 1 if event.get("worn") else 0
    rating = int(event.get("rating", 5))

    outfit_data = event.get("outfit") or {}
    items = outfit_data.get("items") or event.get("items") or []
    reason = outfit_data.get("reason") or event.get("reason") or event.get("explanation") or ""
    title = event.get("outfit_title") or f"{occasion.title()} Look"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM planned_outfits WHERE user_id = ? AND date = ?", (user_id, date_key))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE planned_outfits
            SET occasion = ?, weather = ?, outfit_title = ?, items_json = ?, reason = ?, worn = ?, rating = ?
            WHERE id = ?
        """, (occasion, weather, title, json.dumps(items), reason, worn, rating, existing["id"]))
    else:
        cursor.execute("""
            INSERT INTO planned_outfits (user_id, date, occasion, weather, outfit_title, items_json, reason, worn, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, date_key, occasion, weather, title, json.dumps(items), reason, worn, rating))

    conn.commit()
    conn.close()

    event_resp = {
        **event,
        "key": date_key,
        "date": date_key,
        "occasion": occasion,
        "outfit_title": title,
        "items": items,
        "reason": reason,
        "worn": bool(worn),
    }
    return {"status": "created", "item": event_resp}

@app.patch("/api/calendar/{key}")
def update_calendar_event(key: str, event: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM planned_outfits WHERE user_id = ? AND date = ?", (user_id, key))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Calendar event not found.")

    row = dict(existing)
    worn = 1 if event.get("worn") else (0 if "worn" in event else row.get("worn", 0))
    rating = event.get("rating", row.get("rating", 5))
    occasion = event.get("occasion", row["occasion"])

    cursor.execute("""
        UPDATE planned_outfits SET worn = ?, rating = ?, occasion = ? WHERE id = ?
    """, (worn, rating, occasion, row["id"]))
    conn.commit()
    conn.close()

    row["worn"] = bool(worn)
    row["rating"] = rating
    row["key"] = key
    return {"status": "updated", "item": row}

@app.delete("/api/calendar/{key}")
def delete_calendar_event(key: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM planned_outfits WHERE user_id = ? AND date = ?", (user_id, key))
    conn.commit()
    conn.close()
    return {"status": "deleted", "key": key}

# ================================================================
# HISTORY API
# ================================================================

@app.get("/api/history")
def get_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = get_db()
    cursor = conn.cursor()

    # Fetch both marked worn outfits from calendar and past generations
    cursor.execute("SELECT * FROM planned_outfits WHERE user_id = ? AND worn = 1 ORDER BY date DESC", (user_id,))
    worn_rows = cursor.fetchall()

    cursor.execute("SELECT * FROM outfit_history WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,))
    hist_rows = cursor.fetchall()
    conn.close()

    history_items = []
    for r in worn_rows:
        d = dict(r)
        items_data = []
        try:
            items_data = json.loads(d["items_json"])
        except Exception:
            pass
        history_items.append({
            "id": f"worn-{d['id']}",
            "date": d["date"],
            "occasion": d["occasion"],
            "items": items_data,
            "reason": d.get("reason") or "Worn look from your calendar",
            "compatibility_score": 0.95,
        })

    for r in hist_rows:
        d = dict(r)
        outfits = []
        try:
            outfits = json.loads(d["outfits_json"])
        except Exception:
            pass
        if outfits:
            top_outfit = outfits[0]
            created_date = (d.get("created_at") or "").split(" ")[0] or datetime.now().strftime("%Y-%m-%d")
            history_items.append({
                "id": f"gen-{d['id']}",
                "date": created_date,
                "occasion": d.get("occasion") or "Generated Outfit",
                "items": top_outfit.get("items", []),
                "reason": top_outfit.get("explanation") or d.get("weather_context", ""),
                "compatibility_score": 0.92,
            })

    return {"count": len(history_items), "items": history_items}

RECOMMENDATION_CACHE = {}

def invalidate_user_recommendation_cache(user_id: int):
    prefix = f"{user_id}_"
    keys_to_del = [k for k in list(RECOMMENDATION_CACHE.keys()) if k.startswith(prefix)]
    for k in keys_to_del:
        RECOMMENDATION_CACHE.pop(k, None)

# ================================================================
# AI OUTFIT GENERATION - PERSONALIZED BY USER PERSONA
# ================================================================

@app.post("/api/outfits/generate")
def generate_outfits(
    request: OutfitRequest,
    current_user: dict = Depends(get_current_user),
):
    occasion = request.occasion.strip()
    if not occasion:
        raise HTTPException(status_code=400, detail="Occasion is required.")

    user_id = current_user["id"]
    user_dir = get_user_wardrobe_dir(user_id)

    # Fetch DB item metadata mapping for this user
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wardrobe_items WHERE user_id = ?", (user_id,))
    db_items = {r["filename"].lower(): format_db_item(dict(r)) for r in cursor.fetchall()}
    conn.close()

    if not db_items:
        raise HTTPException(status_code=400, detail="Your wardrobe is empty. Add clothing items first to build looks.")

    # Collect images in user's personal wardrobe
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".jfif"}
    wardrobe_paths = sorted(
        [p for p in user_dir.iterdir() if p.is_file() and p.suffix.lower() in extensions],
        key=lambda p: p.name.lower()
    )

    weather = get_weather_context(request.temperature_c, request.rain)

    # Check cache first for instant sub-millisecond response
    cache_key = f"{user_id}_{occasion.lower()}_{round(request.temperature_c)}_{request.rain}"
    if cache_key in RECOMMENDATION_CACHE:
        print(f"[Cache Hit] Returning instant cached outfits for {cache_key}")
        return RECOMMENDATION_CACHE[cache_key]

    print()
    print("=" * 70)
    print(f"GEMINI MULTI-USER OUTFIT REQUEST [{current_user['name']} - {current_user['style_persona']}]")
    print("=" * 70)
    print(f"Occasion: {occasion}")
    print(f"Temperature: {request.temperature_c}°C ({weather})")
    print(f"Rain: {request.rain}")
    print(f"User wardrobe items: {len(wardrobe_paths)}")

    user_persona = {
        "name": current_user["name"],
        "role": current_user.get("role", "Fashion Enthusiast"),
        "style_persona": current_user.get("style_persona", "Casual"),
        "preferred_colors": current_user.get("preferred_colors", []),
        "bio": current_user.get("bio", ""),
    }

    try:
        results = recommend_outfits(
            wardrobe_dir=user_dir,
            occasion=occasion,
            weather=weather,
            user_persona=user_persona,
            items_metadata=list(db_items.values()),
        )
    except Exception as exc:
        print("Gemini recommendation error, falling back to smart rules:", exc)
        from recommender.gemini_recommender import smart_fallback_outfits
        results = smart_fallback_outfits(
            occasion=occasion,
            weather=weather,
            user_persona=user_persona,
            items=list(db_items.values()),
        )

    outfits = []
    for result in results.get("outfits", []):
        item_ids = result.get("items", [])
        enriched_items = []

        for filename in item_ids:
            clean_name = Path(str(filename)).name.lower()
            if clean_name in db_items:
                enriched_items.append(db_items[clean_name])
            else:
                # Fallback to local file matching
                match = next((p for p in wardrobe_paths if p.name.lower() == clean_name), None)
                if match:
                    enriched_items.append({
                        "id": match.stem,
                        "filename": match.name,
                        "url": f"/wardrobe/{user_id}/{match.name}",
                        "name": match.stem.replace("_", " ").title(),
                        "category": "top",
                        "group": "top",
                    })

        if not enriched_items:
            continue

        rank_idx = len(outfits)
        outfits.append({
            "rank": result.get("rank", rank_idx + 1),
            "item_ids": [it["id"] for it in enriched_items],
            "items": enriched_items,
            "ranking_mode": "gemini",
            "explanation": result.get("reason", "Curated especially for your personal style and aesthetic."),
            "user_persona": current_user["style_persona"],
            "compatibility_score": result.get("compatibility_score", max(0.85, round(0.97 - rank_idx * 0.03, 2))),
            "occasion_score": result.get("occasion_score", max(0.88, round(0.99 - rank_idx * 0.03, 2))),
            "weather_score": result.get("weather_score", max(0.85, round(0.95 - rank_idx * 0.02, 2))),
            "vit_score": result.get("vit_score", max(0.86, round(0.97 - rank_idx * 0.03, 2))),
            "garment_compatibility_score": result.get("garment_compatibility_score", max(0.86, round(0.96 - rank_idx * 0.03, 2))),
        })

    if not outfits:
        raise HTTPException(status_code=500, detail="Gemini returned no valid outfits.")

    # Save to history table
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO outfit_history (user_id, generation_id, occasion, temperature_c, rain, weather_context, outfits_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        str(uuid.uuid4()),
        occasion,
        request.temperature_c,
        1 if request.rain else 0,
        weather,
        json.dumps(outfits),
    ))
    conn.commit()
    conn.close()

    response_payload = {
        "user": {
            "name": current_user["name"],
            "style_persona": current_user["style_persona"],
        },
        "occasion": occasion,
        "temperature_c": request.temperature_c,
        "rain": request.rain,
        "weather_context": weather,
        "wardrobe_items": len(wardrobe_paths),
        "ranking_mode": "gemini",
        "outfits": outfits,
    }
    RECOMMENDATION_CACHE[cache_key] = response_payload
    return response_payload

# ================================================================
# RUN DIRECTLY
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastApi:app", host="127.0.0.1", port=8000, reload=True)