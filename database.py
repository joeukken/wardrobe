import os
import json
import sqlite3
import hashlib
import random
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "smart_wardrobe.db"
SEED_WARDROBE_DIR = BASE_DIR / "wardrobe"
USERS_WARDROBES_DIR = BASE_DIR / "user_wardrobes"
USERS_WARDROBES_DIR.mkdir(exist_ok=True)

# 20 diverse users with unique personal fashion personas and preferences
DEFAULT_USERS = [
    {
        "username": "emma_watson",
        "name": "Emma Watson",
        "role": "College Student",
        "style": "Casual & Chic",
        "preferred_colors": ["White", "Blue", "Black"],
        "temp_pref": "Warm",
        "bio": "Loves denim, effortless daily styles, and trendy sneakers."
    },
    {
        "username": "liam_vance",
        "name": "Liam Vance",
        "role": "Corporate Consultant",
        "style": "Formal Business",
        "preferred_colors": ["Navy", "Charcoal", "White"],
        "temp_pref": "Cool",
        "bio": "Crisp shirts, structured jackets, tailored trousers."
    },
    {
        "username": "sophia_chen",
        "name": "Sophia Chen",
        "role": "Architect",
        "style": "Minimalist Monochrome",
        "preferred_colors": ["Black", "Grey", "Off-White"],
        "temp_pref": "Neutral",
        "bio": "Clean lines, monotone outfits, timeless silhouettes."
    },
    {
        "username": "noah_miller",
        "name": "Noah Miller",
        "role": "Graphic Designer",
        "style": "Urban Streetwear",
        "preferred_colors": ["Black", "Olive", "Rust"],
        "temp_pref": "Cool",
        "bio": "Layered shrugs, jackets, relaxed shorts, bold accessories."
    },
    {
        "username": "olivia_garcia",
        "name": "Olivia Garcia",
        "role": "Yoga Instructor",
        "style": "Bohemian Romantic",
        "preferred_colors": ["Floral", "Cream", "Earthy"],
        "temp_pref": "Warm",
        "bio": "Flowy dresses, lightweight shrugs, breezy skirts."
    },
    {
        "username": "ethan_davis",
        "name": "Ethan Davis",
        "role": "Fitness Coach",
        "style": "Athleisure & Sporty",
        "preferred_colors": ["Grey", "Navy", "Brights"],
        "temp_pref": "Warm",
        "bio": "Comfort-first stretch tops, light bottoms, ready for active days."
    },
    {
        "username": "ava_martinez",
        "name": "Ava Martinez",
        "role": "Event Producer",
        "style": "Evening Glamour",
        "preferred_colors": ["Emerald", "Black", "Burgundy"],
        "temp_pref": "Cool",
        "bio": "Statement dresses, elegant layers, date night & cocktail ready."
    },
    {
        "username": "lucas_kim",
        "name": "Lucas Kim",
        "role": "Software Engineer",
        "style": "Smart Casual",
        "preferred_colors": ["Beige", "Denim", "White"],
        "temp_pref": "Neutral",
        "bio": "Chinos, layering knitwear, clean shirts for tech office."
    },
    {
        "username": "mia_anderson",
        "name": "Mia Anderson",
        "role": "Art Curator",
        "style": "Retro & Vintage 90s",
        "preferred_colors": ["Brown", "Denim Blue", "Mustard"],
        "temp_pref": "Cool",
        "bio": "High-waist skirts, vintage outerwear, layered shrugs."
    },
    {
        "username": "jackson_taylor",
        "name": "Jackson Taylor",
        "role": "Wildlife Photographer",
        "style": "Rugged Outdoor",
        "preferred_colors": ["Khaki", "Forest Green", "Brown"],
        "temp_pref": "Cold",
        "bio": "Heavy jackets, tough pants, weather-ready all-season gear."
    },
    {
        "username": "isabella_moore",
        "name": "Isabella Moore",
        "role": "Law Student",
        "style": "Preppy Classic",
        "preferred_colors": ["Navy", "Pastels", "White"],
        "temp_pref": "Neutral",
        "bio": "Pleated skirts, collared tops, neat outer jackets."
    },
    {
        "username": "aiden_thomas",
        "name": "Aiden Thomas",
        "role": "Creative Director",
        "style": "Dark Avant-Garde",
        "preferred_colors": ["Jet Black", "Dark Charcoal"],
        "temp_pref": "Cool",
        "bio": "All-black ensembles, architectural layers, statement drape."
    },
    {
        "username": "charlotte_jackson",
        "name": "Charlotte Jackson",
        "role": "Travel Vlogger",
        "style": "Resort & Vacation",
        "preferred_colors": ["Coral", "Turquoise", "White"],
        "temp_pref": "Hot",
        "bio": "Sun dresses, breezy shorts, effortless summer daywear."
    },
    {
        "username": "mason_white",
        "name": "Mason White",
        "role": "Industrial Designer",
        "style": "Nordic Cosy",
        "preferred_colors": ["Oatmeal", "Soft Grey", "Slate"],
        "temp_pref": "Cold",
        "bio": "Warm layers, shrugs, jackets, insulating comfort."
    },
    {
        "username": "amelia_harris",
        "name": "Amelia Harris",
        "role": "Marketing Executive",
        "style": "Executive Workwear",
        "preferred_colors": ["Camel", "Ivory", "Black"],
        "temp_pref": "Neutral",
        "bio": "Power dresses, tailored trousers, sleek structured jackets."
    },
    {
        "username": "benjamin_martin",
        "name": "Benjamin Martin",
        "role": "Music Producer",
        "style": "Indie Alternative",
        "preferred_colors": ["Plaid", "Washed Denim", "Black"],
        "temp_pref": "Cool",
        "bio": "Relaxed shorts, oversized jackets, casual band tops."
    },
    {
        "username": "harper_clark",
        "name": "Harper Clark",
        "role": "Illustrator",
        "style": "Vibrant Eclectic",
        "preferred_colors": ["Yellow", "Cobalt", "Pink"],
        "temp_pref": "Warm",
        "bio": "Fun prints, mixed textures, bold color block outfits."
    },
    {
        "username": "elijah_lewis",
        "name": "Elijah Lewis",
        "role": "Product Manager",
        "style": "Modern Commuter",
        "preferred_colors": ["Graphite", "Navy", "Heather"],
        "temp_pref": "Cool",
        "bio": "Functional pants, lightweight waterproof jackets, versatile tops."
    },
    {
        "username": "evelyn_robinson",
        "name": "Evelyn Robinson",
        "role": "Interior Stylist",
        "style": "Quiet Luxury",
        "preferred_colors": ["Silk Cream", "Taupe", "Espresso"],
        "temp_pref": "Neutral",
        "bio": "Sophisticated skirts, cashmere-look shrugs, tailored staples."
    },
    {
        "username": "alexander_walker",
        "name": "Alexander Walker",
        "role": "Professor",
        "style": "Heritage Classic",
        "preferred_colors": ["Tweed", "Brown", "Burgundy"],
        "temp_pref": "Cold",
        "bio": "Classic wool-look jackets, structured pants, timeless collared tops."
    }
]

SEED_ITEMS_METADATA = {
    "top.jfif": {"name": "Basic Crewneck Top", "category": "top", "group": "top", "style": "casual", "colors": ["White", "Beige"], "warmth": 2},
    "top1.jfif": {"name": "Linen Long-sleeve Top", "category": "top", "group": "top", "style": "smart casual", "colors": ["Blue", "Denim"], "warmth": 2},
    "top2.jfif": {"name": "Casual Cotton Tee", "category": "top", "group": "top", "style": "casual", "colors": ["Grey", "Black"], "warmth": 1},
    "top3.jfif": {"name": "Silk Blend Sleeveless Top", "category": "top", "group": "top", "style": "elegant", "colors": ["Pastel", "Cream"], "warmth": 1},
    "top4.jfif": {"name": "Fitted Ribbed Knit Top", "category": "top", "group": "top", "style": "minimalist", "colors": ["Black"], "warmth": 2},
    "top5.jfif": {"name": "Boho Printed Top", "category": "top", "group": "top", "style": "boho", "colors": ["Floral", "Multi"], "warmth": 1},
    "bottom1.jfif": {"name": "Dark Wash Denim Jeans", "category": "pants", "group": "bottom", "style": "casual", "colors": ["Blue", "Navy"], "warmth": 3},
    "bottom2.jfif": {"name": "Wide Leg Chino Pants", "category": "pants", "group": "bottom", "style": "smart casual", "colors": ["Khaki", "Beige"], "warmth": 2},
    "bottom3.jfif": {"name": "Casual Stretch Trousers", "category": "pants", "group": "bottom", "style": "casual", "colors": ["Charcoal", "Black"], "warmth": 2},
    "pants.jfif": {"name": "Classic Tailored Slacks", "category": "pants", "group": "bottom", "style": "business", "colors": ["Black"], "warmth": 3},
    "pants1.jfif": {"name": "Relaxed Straight-Leg Pants", "category": "pants", "group": "bottom", "style": "minimalist", "colors": ["Slate", "Grey"], "warmth": 2},
    "shorts1.jfif": {"name": "Summer Tailored Shorts", "category": "shorts", "group": "bottom", "style": "casual", "colors": ["Beige"], "warmth": 1},
    "shorts2.jfif": {"name": "Athletic Daily Shorts", "category": "shorts", "group": "bottom", "style": "sporty", "colors": ["Navy", "Black"], "warmth": 1},
    "skirt.jfif": {"name": "Pleated A-Line Midi Skirt", "category": "skirt", "group": "bottom", "style": "preppy", "colors": ["Navy", "Pattern"], "warmth": 2},
    "skirt2.jfif": {"name": "Sleek High-Waist Pencil Skirt", "category": "skirt", "group": "bottom", "style": "business", "colors": ["Black"], "warmth": 2},
    "dress.jfif": {"name": "Summer Floral Day Dress", "category": "dress", "group": "one-piece", "style": "boho", "colors": ["Floral", "Coral"], "warmth": 1},
    "dress1.jfif": {"name": "Cocktail Evening Dress", "category": "dress", "group": "one-piece", "style": "glamour", "colors": ["Emerald", "Black"], "warmth": 2},
    "jacket.jfif": {"name": "Heavy Duty Parka Jacket", "category": "jacket", "group": "outerwear", "style": "outdoor", "colors": ["Khaki", "Green"], "warmth": 5},
    "jacket2.jfif": {"name": "Structured Tailored Blazer", "category": "jacket", "group": "outerwear", "style": "business", "colors": ["Navy", "Charcoal"], "warmth": 3},
    "jacket3.jfif": {"name": "Modern Leather Bomber Jacket", "category": "jacket", "group": "outerwear", "style": "streetwear", "colors": ["Black"], "warmth": 4},
    "shrug.jfif": {"name": "Lightweight Cropped Shrug", "category": "shrug", "group": "outerwear", "style": "boho", "colors": ["Cream", "White"], "warmth": 2},
    "shrug2.jfif": {"name": "Cosy Open Knit Cardigan Shrug", "category": "shrug", "group": "outerwear", "style": "nordic", "colors": ["Soft Grey"], "warmth": 3},
}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT,
        style_persona TEXT,
        preferred_colors TEXT,
        temp_pref TEXT,
        bio TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wardrobe_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        group_type TEXT NOT NULL,
        style TEXT,
        colors TEXT,
        warmth_level INTEGER DEFAULT 2,
        is_favorite INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS planned_outfits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        occasion TEXT NOT NULL,
        weather TEXT,
        outfit_title TEXT,
        items_json TEXT NOT NULL,
        reason TEXT,
        rating INTEGER DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        fav_key TEXT NOT NULL,
        item_data_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, fav_key),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outfit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        generation_id TEXT NOT NULL,
        occasion TEXT,
        temperature_c REAL,
        rain INTEGER,
        weather_context TEXT,
        outfits_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

def seed_users_and_wardrobes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM wardrobe_items")
    count = cursor.fetchone()["cnt"]
    conn.close()

    if count < 200:
        try:
            from migrate_10_dresses import migrate_database
            migrate_database()
        except Exception as e:
            print("Migration warning:", e)
    else:
        print("Database initialized with 20 distinct cultural closets and 10 items each!")

if __name__ == "__main__":
    init_database()
    seed_users_and_wardrobes()
