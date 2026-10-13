import os
import sys
import json
import sqlite3
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "smart_wardrobe.db"
USER_WARDROBES_DIR = BASE_DIR / "user_wardrobes"
USER_WARDROBES_DIR.mkdir(exist_ok=True)
CACHE_DIR = BASE_DIR / ".image_cache"
CACHE_DIR.mkdir(exist_ok=True)
WARDROBE_DIR = BASE_DIR / "wardrobe"

# Curated base fashion image URLs from Unsplash (diverse ethnic & global garments)
CURATED_IMAGE_URLS = [
    # Ethnic wear, sarees, lehengas, kurtas
    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&q=80", # Red/Gold Indian silk dress
    "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=600&q=80", # Traditional Indian silk
    "https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&q=80", # Ethnic festive kurti
    "https://images.unsplash.com/photo-1609357605129-26f69add5d6e?w=600&q=80", # Elegant traditional tunic
    "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=600&q=80", # Patterned ethnic wear
    "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&q=80", # Yellow/Golden cotton kurti
    "https://images.unsplash.com/photo-1610030469668-932d0c273c52?w=600&q=80", # Pastel Indian ensemble
    "https://images.unsplash.com/photo-1583391733975-081e64627b0c?w=600&q=80", # Deep red festive wear
    "https://images.unsplash.com/photo-1617627143990-eb83f885df48?w=600&q=80", # Embroidered top
    "https://images.unsplash.com/photo-1610030470298-6323bc05e267?w=600&q=80", # Silk dupatta drape
    # Modern & Western dresses
    "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&q=80", # Classic red dress
    "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&q=80", # Floral print dress
    "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=600&q=80", # Breezy white summer dress
    "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=600&q=80", # Elegant evening gown
    "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&q=80", # High-fashion autumn trench
    "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&q=80", # Editorial chic drape
    "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=600&q=80", # Pastel blazer & slacks
    "https://images.unsplash.com/photo-1525507119028-ed4c629a60a3?w=600&q=80", # Clean casual wear
    "https://images.unsplash.com/photo-1485968579580-b6d095142e6e?w=600&q=80", # Minimalist knit & skirt
    "https://images.unsplash.com/photo-1502716119720-b23a93e5fe1b?w=600&q=80", # Mustard yellow dress
    # Tops, Blouses & Shirts
    "https://images.unsplash.com/photo-1551803091-e20673f15770?w=600&q=80", # Silk collared blouse
    "https://images.unsplash.com/photo-1589902860314-e910697dea18?w=600&q=80", # Relaxed linen shirt
    "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=600&q=80", # Cozy ribbed knit
    "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=600&q=80", # Denim shirt / jacket
    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&q=80", # Graphic vintage tee
    # Jackets, Blazers & Shrugs
    "https://images.unsplash.com/photo-1544441893-675973e31985?w=600&q=80", # Tailored beige coat
    "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&q=80", # Leather / bomber jacket
    "https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=600&q=80", # Pinstripe dark blazer
    "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?w=600&q=80", # Casual cardigan shrug
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&q=80", # High fashion portrait
    # Pants, Trousers & Skirts
    "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=600&q=80", # Tailored wide trousers
    "https://images.unsplash.com/photo-1584370848010-d7fe6bc767ec?w=600&q=80", # Pleated midi skirt
    "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&q=80", # Classic blue denim
    "https://images.unsplash.com/photo-1506630448388-4e683c67ddb0?w=600&q=80", # Linen summer trousers
    "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=600&q=80", # High-waist formal pants
]

def load_category_image_pools():
    """Load local cached images grouped strictly by garment category so dresses show dresses, pants show pants, etc."""
    def open_valid(paths):
        imgs = []
        for p in paths:
            if p.exists():
                try:
                    imgs.append(Image.open(p).convert("RGB"))
                except Exception:
                    pass
        if not imgs:
            imgs.append(Image.new("RGB", (500, 650), (245, 240, 230)))
        return imgs

    dress_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [0, 1, 4, 10, 11, 12, 13, 15, 19]] + [WARDROBE_DIR / "dress.jfif", WARDROBE_DIR / "dress1.jfif"]
    top_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [2, 3, 5, 17, 20, 21, 22, 23, 24]] + [WARDROBE_DIR / f"top{s}.jfif" for s in ["", "1", "2", "3", "4", "5"]]
    pants_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [30, 32, 33, 34]] + [WARDROBE_DIR / f"bottom{s}.jfif" for s in ["1", "2", "3"]] + [WARDROBE_DIR / "pants.jfif", WARDROBE_DIR / "pants1.jfif"]
    skirt_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [18, 31]] + [WARDROBE_DIR / "skirt.jfif", WARDROBE_DIR / "skirt2.jfif"]
    jacket_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [14, 16, 25, 26, 27, 29]] + [WARDROBE_DIR / "jacket.jfif", WARDROBE_DIR / "jacket2.jfif", WARDROBE_DIR / "jacket3.jfif"]
    shrug_paths = [CACHE_DIR / f"base_{i}.jpg" for i in [28, 16, 25, 29]] + [WARDROBE_DIR / "shrug.jfif", WARDROBE_DIR / "shrug2.jfif"]

    return {
        "dress": open_valid(dress_paths),
        "top": open_valid(top_paths),
        "pants": open_valid(pants_paths),
        "skirt": open_valid(skirt_paths),
        "jacket": open_valid(jacket_paths),
        "shrug": open_valid(shrug_paths),
    }

def style_image(base_img, tag, occ_label, color_rgb, u_idx=0, i_idx=0, is_kerala=False, is_punjab=False):
    target_w, target_h = 500, 650
    # Apply subtle unique framing/zoom per user & item so every user's garment looks distinct
    centering_x = 0.25 + ((u_idx * 13 + i_idx * 7) % 50) / 100.0
    centering_y = 0.25 + ((u_idx * 11 + i_idx * 5) % 50) / 100.0
    img = ImageOps.fit(base_img, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(centering_x, centering_y))

    # Subtle cultural color wash (8% blend of regional signature color)
    tint = Image.new("RGB", (target_w, target_h), color_rgb)
    img = Image.blend(img, tint, 0.08)
    draw = ImageDraw.Draw(img)

    if is_kerala:
        # Authentic Kerala Kasavu Gold Zari Border at hem
        border_h = 44
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(218, 165, 32))
        draw.line([0, target_h - border_h - 4, target_w, target_h - border_h - 4], fill=(184, 134, 11), width=4)
        draw.line([0, target_h - border_h + 10, target_w, target_h - border_h + 10], fill=(255, 223, 0), width=2)
        overlay = Image.new("RGB", (target_w, target_h), (252, 248, 238))
        img = Image.blend(img, overlay, 0.12)
        draw = ImageDraw.Draw(img)
    elif is_punjab:
        # Vibrant Phulkari geometric embroidered border
        border_h = 40
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(224, 17, 95))
        step = 25
        for x in range(0, target_w, step):
            draw.polygon([(x, target_h), (x + step // 2, target_h - border_h + 4), (x + step, target_h)], fill=(255, 191, 0))
        draw.line([0, target_h - border_h, target_w, target_h - border_h], fill=(0, 168, 107), width=3)
    else:
        # Regional cultural accent border at hem
        border_h = 34
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(22, 18, 16))
        draw.line([0, target_h - border_h, target_w, target_h - border_h], fill=color_rgb, width=4)
        for x in range(16, target_w - 16, 28):
            draw.ellipse([x, target_h - border_h + 12, x + 8, target_h - border_h + 20], fill=color_rgb)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Top-left regional & category pill badge
    pill_w = min(target_w - 24, max(210, len(tag) * 7 + 44))
    pill_h = 30
    pill_x0, pill_y0 = 12, 12
    draw.rounded_rectangle([pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h], radius=6, fill=(18, 18, 22))
    draw.ellipse([pill_x0 + 8, pill_y0 + 9, pill_x0 + 20, pill_y0 + 21], fill=color_rgb)
    draw.text((pill_x0 + 26, pill_y0 + 9), tag.upper(), fill=(245, 245, 245), font=font)

    # Top-right occasion pill badge
    if occ_label:
        occ_text = occ_label.upper()
        occ_w = max(76, len(occ_text) * 7 + 22)
        ox0 = target_w - occ_w - 12
        oy0 = 12
        draw.rounded_rectangle([ox0, oy0, ox0 + occ_w, oy0 + 28], radius=14, fill=(122, 31, 43))
        draw.text((ox0 + 11, oy0 + 8), occ_text, fill=(255, 248, 240), font=font)

    return img


REGIONAL_USERS = [
    # 1. PUNJAB
    {
        "id": 1,
        "name": "Harpreet Kaur",
        "username": "harpreet_kaur",
        "role": "Punjabi Textile Designer & Stylist (Amritsar & Chandigarh)",
        "style_persona": "Punjabi Royal Phulkari & Patiala Heritage",
        "preferred_colors": ["Rani Pink", "Mustard Gold", "Emerald Green", "Royal Blue", "Crimson Red"],
        "temp_pref": "Moderate / Seasonal",
        "bio": "Vibrant hand-embroidered Phulkari dupattas, regal Patiala salwars, silk Anarkalis, Amritsari brocade jackets, and festive Lohri & Baisakhi celebration attire.",
        "badge": "PUNJAB · PHULKARI",
        "color": (224, 17, 95),
        "is_punjab": True,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Phulkari Hand-Embroidered Georgette Anarkali Dress", "dress", "onepiece", "Punjabi Heritage", ["Rani Pink", "Gold"], 2),
            ("item_2.jfif", "Royal Patiala Salwar & Kurti Festive Ensemble", "dress", "onepiece", "Punjabi Heritage", ["Mustard Gold"], 2),
            ("item_3.jfif", "Amritsari Resham Embroidered Silk Kurta", "top", "top", "Punjabi Heritage", ["Emerald Green"], 2),
            ("item_4.jfif", "Pleated Georgette Patiala Salwar Trousers", "pants", "bottom", "Punjabi Heritage", ["Royal Blue"], 2),
            ("item_5.jfif", "Ludhiana Giddha Velvet Embroidered Koti Jacket", "jacket", "outerwear", "Punjabi Heritage", ["Crimson Red"], 3),
            ("item_6.jfif", "Baisakhi Festive Marigold Yellow Kurti", "top", "top", "Punjabi Heritage", ["Marigold Yellow"], 1),
            ("item_7.jfif", "Royal Blue Banarasi Silk Sharara Pants", "pants", "bottom", "Punjabi Heritage", ["Royal Blue"], 2),
            ("item_8.jfif", "Jalandhar Mirror-Work Festive Kaftan Dress", "dress", "onepiece", "Punjabi Heritage", ["Turquoise"], 2),
            ("item_9.jfif", "Chanderi Silk Flared Angrakha Tunic", "top", "top", "Punjabi Heritage", ["Ivory & Gold"], 2),
            ("item_10.jfif", "Crimson Red Brocade Straight Cigarette Pants", "pants", "bottom", "Punjabi Heritage", ["Crimson Red"], 2),
            ("item_11.jfif", "Golden Zari Woven Punjabi Nehru Shrug", "shrug", "outerwear", "Punjabi Heritage", ["Metallic Gold"], 2),
            ("item_12.jfif", "Pastel Mint Green Cotton Kurta Top", "top", "top", "Punjabi Heritage", ["Mint Green"], 1),
            ("item_13.jfif", "Phulkari Border Pleated Flared Ethnic Skirt", "skirt", "bottom", "Punjabi Heritage", ["Black & Multicolored"], 2),
            ("item_14.jfif", "Rani Pink Georgette Tiered Festive Dress", "dress", "onepiece", "Punjabi Heritage", ["Rani Pink"], 2),
            ("item_15.jfif", "Handloom Tussar Silk Short Festive Kurti", "top", "top", "Punjabi Heritage", ["Beige Gold"], 2),
            ("item_16.jfif", "Patiala Heavy Ghera Pure Silk Salwar", "pants", "bottom", "Punjabi Heritage", ["Teal Green"], 2),
            ("item_17.jfif", "Embroidered Velvet Winter Pherun Jacket", "jacket", "outerwear", "Punjabi Heritage", ["Wine Velvet"], 4),
            ("item_18.jfif", "Gold Tissue Silk Peplum Kurti Top", "top", "top", "Punjabi Heritage", ["Gold Tissue"], 2),
            ("item_19.jfif", "Royal Emerald Silk Evening Party Dress", "dress", "onepiece", "Punjabi Heritage", ["Emerald"], 2),
            ("item_20.jfif", "Multicolored Phulkari Handcrafted Open Shrug", "shrug", "outerwear", "Punjabi Heritage", ["Multi Phulkari"], 2),
        ]
    },
    # 2. KERALA
    {
        "id": 2,
        "name": "Ananya Nair",
        "username": "ananya_nair",
        "role": "Classical Dancer & Handloom Curator (Kochi & Trivandrum)",
        "style_persona": "Kerala Kasavu & Temple Border Minimalist Chic",
        "preferred_colors": ["Off-White Kasavu", "Gold Zari", "Temple Red", "Peacock Green", "Lotus Pink"],
        "temp_pref": "Warm / Tropical",
        "bio": "Pure Kerala Kasavu handloom cottons, gold zari border set-mundu drapes, Onam festive attire, handcrafted temple jewelry borders, and breathable coastal linens.",
        "badge": "KERALA · KASAVU",
        "color": (218, 165, 32),
        "is_punjab": False,
        "is_kerala": True,
        "items": [
            ("item_1.jfif", "Traditional Kerala Kasavu Gold Zari Saree Dress", "dress", "onepiece", "Kerala Kasavu", ["Off-White & Gold"], 1),
            ("item_2.jfif", "Kerala Handloom Set-Mundu Draped Ensemble", "dress", "onepiece", "Kerala Kasavu", ["Pure Cream"], 1),
            ("item_3.jfif", "Onam Festive Golden Temple Border Kurti", "top", "top", "Kerala Kasavu", ["Ivory & Gold"], 1),
            ("item_4.jfif", "Kasavu Gold Border Cotton Pleated Skirt", "skirt", "bottom", "Kerala Kasavu", ["Off-White & Gold"], 1),
            ("item_5.jfif", "Kochi Handwoven Raw Cotton Tunic Top", "top", "top", "Kerala Kasavu", ["Pure White"], 1),
            ("item_6.jfif", "Kerala Golden Tissue Peplum Blouse Top", "top", "top", "Kerala Kasavu", ["Metallic Gold"], 2),
            ("item_7.jfif", "Alappuzha Backwater Linen Culotte Trousers", "pants", "bottom", "Kerala Kasavu", ["Sand Linen"], 1),
            ("item_8.jfif", "Malabar Peacock Green Silk Slip Dress", "dress", "onepiece", "Kerala Kasavu", ["Peacock Green"], 2),
            ("item_9.jfif", "Thrissur Golden Brocade Tailored Crop Jacket", "jacket", "outerwear", "Kerala Kasavu", ["Gold Brocade"], 2),
            ("item_10.jfif", "Temple Red Lotus Border Cotton Kurti", "top", "top", "Kerala Kasavu", ["Temple Red"], 1),
            ("item_11.jfif", "Handspun Kasavu Zari Border Open Shrug", "shrug", "outerwear", "Kerala Kasavu", ["Cream & Gold"], 1),
            ("item_12.jfif", "Kovalam Coastal Breathable Linen Top", "top", "top", "Kerala Kasavu", ["Sky Blue"], 1),
            ("item_13.jfif", "Kozhikode Handloom White Cotton Dhoti Pants", "pants", "bottom", "Kerala Kasavu", ["Off-White"], 1),
            ("item_14.jfif", "Munnar Mountain Tea-Green Silk Maxi Dress", "dress", "onepiece", "Kerala Kasavu", ["Tea Green"], 2),
            ("item_15.jfif", "Kumarakom Breezy Boatneck Khadi Tunic", "top", "top", "Kerala Kasavu", ["Natural Khadi"], 1),
            ("item_16.jfif", "Kerala Gold Tissue Tailored Formal Pants", "pants", "bottom", "Kerala Kasavu", ["Gold Tissue"], 2),
            ("item_17.jfif", "Varkala Sunset Coral Handloom Kurta", "top", "top", "Kerala Kasavu", ["Coral Lotus"], 1),
            ("item_18.jfif", "Mattancherry Vintage Spice Route Shrug", "shrug", "outerwear", "Kerala Kasavu", ["Terracotta Gold"], 2),
            ("item_19.jfif", "Royal Travancore Velvet & Zari Evening Gown", "dress", "onepiece", "Kerala Kasavu", ["Royal Maroon"], 3),
            ("item_20.jfif", "Kasavu Golden Striped Handloom Pencil Skirt", "skirt", "bottom", "Kerala Kasavu", ["Kasavu Gold"], 1),
        ]
    },
    # 3. RAJASTHAN
    {
        "id": 3,
        "name": "Diya Rathore",
        "username": "diya_rathore",
        "role": "Heritage Jewelry & Royal Textile Historian (Jaipur & Udaipur)",
        "style_persona": "Jaipur Bandhani, Leheriya & Gota Patti Grandeur",
        "preferred_colors": ["Marigold Yellow", "Ruby Red", "Royal Saffron", "Turquoise", "Emerald"],
        "temp_pref": "Warm / Desert",
        "bio": "Vibrant Bandhani tie-dye, Leheriya chiffon waves, intricate Gota Patti handwork, mirror-embellished kotis, and royal Mewari heritage cuts.",
        "badge": "RAJASTHAN · BANDHANI",
        "color": (255, 69, 0),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Jaipur Bandhani Silk Flared Gown Dress", "dress", "onepiece", "Rajasthani Royal", ["Ruby Red"], 2),
            ("item_2.jfif", "Leheriya Chiffon Tiered Sunset Maxi Dress", "dress", "onepiece", "Rajasthani Royal", ["Marigold & Pink"], 1),
            ("item_3.jfif", "Udaipur Gota Patti Embroidered Angrakha Kurti", "top", "top", "Rajasthani Royal", ["Royal Saffron"], 2),
            ("item_4.jfif", "Jodhpur Royal Jodhpuri Tailored Trousers", "pants", "bottom", "Rajasthani Royal", ["Ivory Linen"], 2),
            ("item_5.jfif", "Shekhawati Mirror-Work Velvet Koti Jacket", "jacket", "outerwear", "Rajasthani Royal", ["Midnight Blue"], 3),
            ("item_6.jfif", "Marigold Block-Print Flared Chaniya Skirt", "skirt", "bottom", "Rajasthani Royal", ["Marigold Yellow"], 2),
            ("item_7.jfif", "Sanganeri Indigo Block-Print Cotton Kurta", "top", "top", "Rajasthani Royal", ["Indigo Blue"], 1),
            ("item_8.jfif", "Amber Fort Royal Silk Evening Kaftan Dress", "dress", "onepiece", "Rajasthani Royal", ["Emerald Green"], 2),
            ("item_9.jfif", "Bikaner Raw Silk Embroidered Crop Shrug", "shrug", "outerwear", "Rajasthani Royal", ["Desert Sand"], 2),
            ("item_10.jfif", "Pushkar Desert Camel Raw Linen Pants", "pants", "bottom", "Rajasthani Royal", ["Camel Beige"], 1),
            ("item_11.jfif", "Gota Patti Border Tailored Evening Blazer", "jacket", "outerwear", "Rajasthani Royal", ["Deep Maroon"], 3),
            ("item_12.jfif", "Bagru Mud-Resist Printed Peplum Top", "top", "top", "Rajasthani Royal", ["Earthy Brown"], 1),
            ("item_13.jfif", "Chittorgarh Flared Cotton Gathered Skirt", "skirt", "bottom", "Rajasthani Royal", ["Turquoise"], 2),
            ("item_14.jfif", "Jaipur Hand-Tie Bandhej Slip Day Dress", "dress", "onepiece", "Rajasthani Royal", ["Sunset Coral"], 1),
            ("item_15.jfif", "Royal Mewari High-Neck Silk Blouse", "top", "top", "Rajasthani Royal", ["Antique Gold"], 2),
            ("item_16.jfif", "Kota Doria Lightweight Cotton Salwar", "pants", "bottom", "Rajasthani Royal", ["Pure White"], 1),
            ("item_17.jfif", "Thar Desert Reversible Quilted Velvet Jacket", "jacket", "outerwear", "Rajasthani Royal", ["Rust Orange"], 4),
            ("item_18.jfif", "Ajmer Dargah Floral Printed Lawn Top", "top", "top", "Rajasthani Royal", ["Mint Sage"], 1),
            ("item_19.jfif", "Jaisalmer Golden Fort Evening Silk Dress", "dress", "onepiece", "Rajasthani Royal", ["Golden Mustard"], 2),
            ("item_20.jfif", "Artisanal Mirror-Work Short Shrug", "shrug", "outerwear", "Rajasthani Royal", ["Black & Mirrors"], 2),
        ]
    },
    # 4. WEST BENGAL
    {
        "id": 4,
        "name": "Ishita Banerjee",
        "username": "ishita_banerjee",
        "role": "Literary Critic & Folk Art Curator (Kolkata)",
        "style_persona": "Bengal Tant, Jamdani & Kantha Stitch Elegance",
        "preferred_colors": ["Lal-Paad White", "Crimson", "Tussar Beige", "Midnight Indigo", "Mustard"],
        "temp_pref": "Moderate / Tropical",
        "bio": "Pristine white handloom with scarlet borders, heirloom Jamdani weaves, Kantha stitch threadwork, Shantiniketan batik kurtas, and intellectual Kolkata grace.",
        "badge": "BENGAL · JAMDANI",
        "color": (178, 34, 34),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Lal-Paad Red & White Handloom Tant Saree Dress", "dress", "onepiece", "Bengal Heritage", ["White & Red"], 1),
            ("item_2.jfif", "Dhaka Jamdani Floral Woven Maxi Gown", "dress", "onepiece", "Bengal Heritage", ["Pure Black & Gold"], 2),
            ("item_3.jfif", "Kantha Stitch Embroidered Silk Kurta Top", "top", "top", "Bengal Heritage", ["Tussar Beige"], 2),
            ("item_4.jfif", "Kolkata Tramway Pleated Linen Wide Trousers", "pants", "bottom", "Bengal Heritage", ["Charcoal Grey"], 1),
            ("item_5.jfif", "Shantiniketan Leather-Applique Artisan Vest", "jacket", "outerwear", "Bengal Heritage", ["Terracotta"], 2),
            ("item_6.jfif", "Baluchari Figural Motif Tailored Midi Skirt", "skirt", "bottom", "Bengal Heritage", ["Crimson Silk"], 2),
            ("item_7.jfif", "College Street Crisp Muslin Poplin Blouse", "top", "top", "Bengal Heritage", ["Ivory"], 1),
            ("item_8.jfif", "Murshidabad Silk Printed Cocktail Dress", "dress", "onepiece", "Bengal Heritage", ["Peacock Teal"], 2),
            ("item_9.jfif", "Bishnupur Terracotta Hand-Spun Woolen Shrug", "shrug", "outerwear", "Bengal Heritage", ["Brick Red"], 3),
            ("item_10.jfif", "Bengal Khadi Relaxed Drawstring Pants", "pants", "bottom", "Bengal Heritage", ["Natural Off-White"], 1),
            ("item_11.jfif", "Swadeshi Cotton Tailored Nehru Jacket", "jacket", "outerwear", "Bengal Heritage", ["Indigo Blue"], 2),
            ("item_12.jfif", "Howrah Bridge Sunset Orange Linen Kurti", "top", "top", "Bengal Heritage", ["Marigold Orange"], 1),
            ("item_13.jfif", "Tangail Handloom Border Pleated Skirt", "skirt", "bottom", "Bengal Heritage", ["Mustard Yellow"], 1),
            ("item_14.jfif", "Durga Puja Festive Scarlet Silk Evening Dress", "dress", "onepiece", "Bengal Heritage", ["Scarlet Red"], 2),
            ("item_15.jfif", "Kumartuli Clay-Tone Raw Cotton Smock Top", "top", "top", "Bengal Heritage", ["Earthy Ochre"], 1),
            ("item_16.jfif", "Calcutta Club Formal Flannel Slacks", "pants", "bottom", "Bengal Heritage", ["Dark Slate"], 3),
            ("item_17.jfif", "Darjeeling Mountain Tweed Tailored Blazer", "jacket", "outerwear", "Bengal Heritage", ["Forest Green"], 4),
            ("item_18.jfif", "Hooghly River Breezy Boatneck Top", "top", "top", "Bengal Heritage", ["Sky Indigo"], 1),
            ("item_19.jfif", "Kalighat Motif Modern Fusion Wrap Dress", "dress", "onepiece", "Bengal Heritage", ["Black & Ochre"], 2),
            ("item_20.jfif", "Kantha Threadwork Open Front Cropped Shrug", "shrug", "outerwear", "Bengal Heritage", ["Multi-Thread Silk"], 2),
        ]
    },
    # 5. KASHMIR
    {
        "id": 5,
        "name": "Zoya Mir",
        "username": "zoya_mir",
        "role": "Pashmina Artisan & Carpet Atelier Director (Srinagar)",
        "style_persona": "Kashmiri Pheran, Tilla Embroidery & Royal Velvet",
        "preferred_colors": ["Saffron", "Chinar Rust", "Velvet Maroon", "Pine Green", "Snow White"],
        "temp_pref": "Cold / Alpine",
        "bio": "Warm cashmere pherans with intricate Tilla gold embroidery, pure Pashmina woolen shrugs, Aari needlework kurtas, and Dal Lake timeless winter royalty.",
        "badge": "KASHMIR · PHERAN",
        "color": (128, 0, 32),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Dal Lake Velvet Tilla Embroidered Pheran Dress", "dress", "onepiece", "Kashmiri Royal", ["Velvet Maroon"], 4),
            ("item_2.jfif", "Gulmarg Snow Cashmere Heavy Winter Wrap Dress", "dress", "onepiece", "Kashmiri Royal", ["Snow Cream"], 4),
            ("item_3.jfif", "Aari Needlework Chinar Leaf Woolen Kurta", "top", "top", "Kashmiri Royal", ["Chinar Rust"], 3),
            ("item_4.jfif", "Kashmiri Flannel Pleated Warm Trousers", "pants", "bottom", "Kashmiri Royal", ["Charcoal"], 3),
            ("item_5.jfif", "Pahalgam Heavy Tweed Longline Winter Coat", "jacket", "outerwear", "Kashmiri Royal", ["Pine Green"], 5),
            ("item_6.jfif", "Srinagar Shikara Silk Embroidered Midi Skirt", "skirt", "bottom", "Kashmiri Royal", ["Antique Gold"], 2),
            ("item_7.jfif", "Pure Pashmina Fine Knit High-Neck Sweater", "top", "top", "Kashmiri Royal", ["Saffron Gold"], 3),
            ("item_8.jfif", "Nishat Bagh Royal Silk Velvet Evening Gown", "dress", "onepiece", "Kashmiri Royal", ["Deep Navy"], 4),
            ("item_9.jfif", "Hand-Spun Pashmina Embroidered Open Shrug", "shrug", "outerwear", "Kashmiri Royal", ["Natural Cream"], 3),
            ("item_10.jfif", "Zabarwan Mountain Thermal Fleece Pants", "pants", "bottom", "Kashmiri Royal", ["Slate Black"], 4),
            ("item_11.jfif", "Kashmiri Silver Tilla Woven Velvet Blazer", "jacket", "outerwear", "Kashmiri Royal", ["Wine Velvet"], 4),
            ("item_12.jfif", "Shalimar Floral Needle-Point Silk Blouse", "top", "top", "Kashmiri Royal", ["Blush Rose"], 2),
            ("item_13.jfif", "Chinar Leaf Printed Heavy Woolen Skirt", "skirt", "bottom", "Kashmiri Royal", ["Burgundy Tartan"], 3),
            ("item_14.jfif", "Pari Mahal Twilight Embroidered Silk Dress", "dress", "onepiece", "Kashmiri Royal", ["Midnight Violet"], 3),
            ("item_15.jfif", "Kashmir Valley Ribbed Woolen Cardigan Top", "top", "top", "Kashmiri Royal", ["Oatmeal Heather"], 3),
            ("item_16.jfif", "Sonamarg Alpine Rugged Wool Slacks", "pants", "bottom", "Kashmiri Royal", ["Dark Grey"], 4),
            ("item_17.jfif", "Weather-Sealed Himalayan Parka Jacket", "jacket", "outerwear", "Kashmiri Royal", ["Olive Drab"], 5),
            ("item_18.jfif", "Saffron Harvest Embroidered Linen Tunic", "top", "top", "Kashmiri Royal", ["Saffron Orange"], 2),
            ("item_19.jfif", "Badamwari Almond Blossom Cashmere Dress", "dress", "onepiece", "Kashmiri Royal", ["Pale Almond"], 3),
            ("item_20.jfif", "Aari Threadwork Cropped Evening Shrug", "shrug", "outerwear", "Kashmiri Royal", ["Ivory & Gold"], 3),
        ]
    },
    # 6. GUJARAT
    {
        "id": 6,
        "name": "Pooja Patel",
        "username": "pooja_patel",
        "role": "Creative Director & Textile Exporter (Ahmedabad & Surat)",
        "style_persona": "Gujarati Patola, Bandhej & Kutchi Artisan Vibrancy",
        "preferred_colors": ["Sindoor Red", "Parrot Green", "Turmeric Yellow", "Royal Blue", "Mirror Silver"],
        "temp_pref": "Warm / Vibrant",
        "bio": "Intricate double-Ikat Patola silk dresses, mirror-work Kutchi jackets, pleated Kediya tops, Navratri ghaghra silhouettes, and colorful Bandhej prints.",
        "badge": "GUJARAT · PATOLA",
        "color": (255, 99, 71),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Patan Patola Double-Ikat Silk Gown Dress", "dress", "onepiece", "Gujarati Royal", ["Sindoor Red"], 2),
            ("item_2.jfif", "Navratri Chaniya Choli Tiered Flared Dress", "dress", "onepiece", "Gujarati Royal", ["Parrot Green"], 2),
            ("item_3.jfif", "Kutchi Mirror-Work Handcrafted Kediya Top", "top", "top", "Gujarati Royal", ["Turmeric Yellow"], 2),
            ("item_4.jfif", "Sabarmati Cotton Relaxed Casual Trousers", "pants", "bottom", "Gujarati Royal", ["Earthy Sand"], 1),
            ("item_5.jfif", "Kutch Rabari Embroidered Mirror-Work Jacket", "jacket", "outerwear", "Gujarati Royal", ["Royal Blue"], 3),
            ("item_6.jfif", "Bandhej Fine Tie-Dye Pleated Midi Skirt", "skirt", "bottom", "Gujarati Royal", ["Crimson"], 2),
            ("item_7.jfif", "Surat Diamond-Jacquard Silk Blouse Top", "top", "top", "Gujarati Royal", ["Silver White"], 2),
            ("item_8.jfif", "Rann of Kutch Sunset Embroidered Maxi Dress", "dress", "onepiece", "Gujarati Royal", ["Coral Pink"], 2),
            ("item_9.jfif", "Ajrakh Block-Print Indigo Cotton Shrug", "shrug", "outerwear", "Gujarati Royal", ["Ajrakh Indigo"], 2),
            ("item_10.jfif", "Ahmedabad Pol Heritage Khadi Chinos", "pants", "bottom", "Gujarati Royal", ["Khadi Cream"], 1),
            ("item_11.jfif", "Heritage Brocade Tailored Ethnic Blazer", "jacket", "outerwear", "Gujarati Royal", ["Emerald Green"], 3),
            ("item_12.jfif", "Kathiawadi Gathered Peplum Kurti Top", "top", "top", "Gujarati Royal", ["Marigold Gold"], 1),
            ("item_13.jfif", "Kutchi Embroidered Flared Cotton Skirt", "skirt", "bottom", "Gujarati Royal", ["Multi Kutchi"], 2),
            ("item_14.jfif", "Gir Forest Organic Cotton Day Dress", "dress", "onepiece", "Gujarati Royal", ["Leaf Green"], 1),
            ("item_15.jfif", "Patola Geometric Motif Silk Tunic Top", "top", "top", "Gujarati Royal", ["Navy & Red"], 2),
            ("item_16.jfif", "Kutch Artisan Handloom Cotton Salwar", "pants", "bottom", "Gujarati Royal", ["Charcoal"], 1),
            ("item_17.jfif", "Quilted Bandhej Reversible Winter Vest", "jacket", "outerwear", "Gujarati Royal", ["Mustard & Red"], 3),
            ("item_18.jfif", "Vadodara Royal Palace Silk Camisole", "top", "top", "Gujarati Royal", ["Champagne"], 1),
            ("item_19.jfif", "Dholavira Earth-Tone Silk Evening Dress", "dress", "onepiece", "Gujarati Royal", ["Terracotta"], 2),
            ("item_20.jfif", "Mirror-Embellished Festive Open Shrug", "shrug", "outerwear", "Gujarati Royal", ["Black Silk"], 2),
        ]
    },
    # 7. TAMIL NADU
    {
        "id": 7,
        "name": "Priya Sundaram",
        "username": "priya_sundaram",
        "role": "Carnatic Musicologist & Silk Curator (Chennai & Kanchipuram)",
        "style_persona": "Kanchipuram Silk & Chettinad Handloom Royalty",
        "preferred_colors": ["Temple Gold", "Manga Malai Mustard", "Kalyana Red", "Peacock Blue", "Forest Green"],
        "temp_pref": "Warm / Coastal",
        "bio": "Heavy gold zari Kanchipuram silk gowns, breezy Chettinad cotton tunics, Madurai Sungudi prints, and classical temple border silhouettes.",
        "badge": "TAMIL NADU · KANCHI",
        "color": (218, 112, 214),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Kanchipuram Gold Zari Brocade Royal Gown Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Kalyana Red & Gold"], 2),
            ("item_2.jfif", "Temple Border Silk Flared Evening Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Peacock Blue"], 2),
            ("item_3.jfif", "Chettinad Handloom Checks Cotton Kurti", "top", "top", "Tamil Temple Heritage", ["Mustard & Maroon"], 1),
            ("item_4.jfif", "Madras Checks Breathable Cotton Trousers", "pants", "bottom", "Tamil Temple Heritage", ["Indigo Checks"], 1),
            ("item_5.jfif", "Thanjavur Temple Gold Embroidered Koti", "jacket", "outerwear", "Tamil Temple Heritage", ["Antique Gold"], 2),
            ("item_6.jfif", "Madurai Sungudi Tie-Dye Pleated Skirt", "skirt", "bottom", "Tamil Temple Heritage", ["Maroon & Gold"], 1),
            ("item_7.jfif", "Mylapore Carnatic Season Silk Blouse Top", "top", "top", "Tamil Temple Heritage", ["Forest Green"], 2),
            ("item_8.jfif", "Marina Beach Sunset Breathable Slip Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Coral Orange"], 1),
            ("item_9.jfif", "Coimbatore Handspun Cotton Open Shrug", "shrug", "outerwear", "Tamil Temple Heritage", ["Natural Cream"], 1),
            ("item_10.jfif", "Chettinadu Heritage Linen Straight Pants", "pants", "bottom", "Tamil Temple Heritage", ["Sand Linen"], 1),
            ("item_11.jfif", "Kanchi Zari Woven Structured Evening Blazer", "jacket", "outerwear", "Tamil Temple Heritage", ["Deep Wine"], 3),
            ("item_12.jfif", "Salem Silk Peplum Kurti Top", "top", "top", "Tamil Temple Heritage", ["Turquoise"], 2),
            ("item_13.jfif", "Temple Pillar Motif Flared Ethnic Skirt", "skirt", "bottom", "Tamil Temple Heritage", ["Black & Gold"], 2),
            ("item_14.jfif", "Kanyakumari Ocean Breeze Handloom Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Aqua Marine"], 1),
            ("item_15.jfif", "Kumbakonam Pure Raw Silk Tunic", "top", "top", "Tamil Temple Heritage", ["Mango Yellow"], 2),
            ("item_16.jfif", "Classical Dhavani Cotton Gathered Slacks", "pants", "bottom", "Tamil Temple Heritage", ["Ivory"], 1),
            ("item_17.jfif", "Ooty Tea-Garden Light Woolen Jacket", "jacket", "outerwear", "Tamil Temple Heritage", ["Pine Green"], 3),
            ("item_18.jfif", "Tanjore Painting Motif Silk Cami Top", "top", "top", "Tamil Temple Heritage", ["Gold & Red"], 1),
            ("item_19.jfif", "Meenakshi Temple Emerald Silk Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Emerald Silk"], 2),
            ("item_20.jfif", "Gold Tissue Temple Border Shrug", "shrug", "outerwear", "Tamil Temple Heritage", ["Gold Tissue"], 1),
        ]
    },
    # 8. MAHARASHTRA
    {
        "id": 8,
        "name": "Aarohi Deshmukh",
        "username": "aarohi_deshmukh",
        "role": "Cinema Production Designer (Mumbai & Pune)",
        "style_persona": "Paithani Silk & Contemporary Maharashtrian Fusion",
        "preferred_colors": ["Peacock Green Paithani", "Golden Yellow", "Royal Purple", "Marathi Red", "Charcoal"],
        "temp_pref": "Warm / Coastal",
        "bio": "Paithani silk dresses with peacock zari pallus, Nauvari-inspired fusion dhoti jumpsuits, Kolhapuri embroidered jackets, and modern South Bombay silhouettes.",
        "badge": "MAHARASHTRA · PAITHANI",
        "color": (75, 0, 130),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Yeola Paithani Silk Peacock Motif Gown Dress", "dress", "onepiece", "Maharashtrian Royal", ["Peacock Green & Gold"], 2),
            ("item_2.jfif", "Nauvari Fusion Draped Silk Jumpsuit Dress", "dress", "onepiece", "Maharashtrian Royal", ["Royal Purple"], 2),
            ("item_3.jfif", "Pune Shaniwar Wada Handloom Cotton Kurta", "top", "top", "Maharashtrian Royal", ["Marathi Red"], 1),
            ("item_4.jfif", "Kolhapuri Hand-Stitched Raw Linen Pants", "pants", "bottom", "Maharashtrian Royal", ["Earthy Tan"], 1),
            ("item_5.jfif", "Mahabaleshwar Winter Cashmere Cardigan Jacket", "jacket", "outerwear", "Maharashtrian Royal", ["Plum"], 3),
            ("item_6.jfif", "Narayan Peth Border Pleated Midi Skirt", "skirt", "bottom", "Maharashtrian Royal", ["Golden Yellow"], 2),
            ("item_7.jfif", "Marine Drive Sunset Breezy Poplin Shirt", "top", "top", "Maharashtrian Royal", ["Sky Blue"], 1),
            ("item_8.jfif", "Bandra Contemporary Linen Slip Dress", "dress", "onepiece", "Maharashtrian Royal", ["Ivory Cream"], 1),
            ("item_9.jfif", "Paithani Border Handwoven Crop Shrug", "shrug", "outerwear", "Maharashtrian Royal", ["Emerald Gold"], 2),
            ("item_10.jfif", "South Bombay Tailored Flannel Trousers", "pants", "bottom", "Maharashtrian Royal", ["Charcoal Black"], 2),
            ("item_11.jfif", "Deccan Club Bespoke Structured Blazer", "jacket", "outerwear", "Maharashtrian Royal", ["Navy Blue"], 3),
            ("item_12.jfif", "Kala Ghoda Art District Cotton Top", "top", "top", "Maharashtrian Royal", ["Monochrome"], 1),
            ("item_13.jfif", "Ajanta Ellora Mural Printed Flared Skirt", "skirt", "bottom", "Maharashtrian Royal", ["Terracotta"], 2),
            ("item_14.jfif", "Alibaug Weekend Coastal Maxi Dress", "dress", "onepiece", "Maharashtrian Royal", ["Olive Linen"], 1),
            ("item_15.jfif", "Solapur Chaddar Inspired Geometric Tunic", "top", "top", "Maharashtrian Royal", ["Indigo"], 1),
            ("item_16.jfif", "Gateway of India Evening Slacks", "pants", "bottom", "Maharashtrian Royal", ["Onyx"], 2),
            ("item_17.jfif", "Lonavala Mist Quilted Weather Jacket", "jacket", "outerwear", "Maharashtrian Royal", ["Forest Green"], 3),
            ("item_18.jfif", "Chanderi Silk Peplum Blouse Top", "top", "top", "Maharashtrian Royal", ["Blush Pink"], 2),
            ("item_19.jfif", "Maratha Empire Royal Velvet Evening Dress", "dress", "onepiece", "Maharashtrian Royal", ["Wine Velvet"], 3),
            ("item_20.jfif", "Peacock Zari Embroidered Silk Shrug", "shrug", "outerwear", "Maharashtrian Royal", ["Gold & Violet"], 2),
        ]
    },
    # 9. ASSAM
    {
        "id": 9,
        "name": "Mayuri Barua",
        "username": "mayuri_barua",
        "role": "Indigenous Weaves Botanist & Stylist (Guwahati)",
        "style_persona": "Assam Muga & Eri Silk Handloom Modernity",
        "preferred_colors": ["Golden Muga", "Eri Ivory", "Gamusa Red", "Assam Indigo", "Forest Fern"],
        "temp_pref": "Moderate / Riverine",
        "bio": "Natural golden Muga silk wrap dresses, thermal Eri wild silk tunics, geometric tribal motif jackets, and Brahmaputra river valley handloom mastery.",
        "badge": "ASSAM · MUGA SILK",
        "color": (218, 165, 32),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Golden Muga Silk Mekhela Chador Fusion Dress", "dress", "onepiece", "Assam Handloom", ["Golden Muga"], 2),
            ("item_2.jfif", "Eri Peace Silk Hand-Spun Wrap Day Dress", "dress", "onepiece", "Assam Handloom", ["Eri Ivory"], 2),
            ("item_3.jfif", "Gamusa Red Border Handloom Cotton Kurti", "top", "top", "Assam Handloom", ["White & Red"], 1),
            ("item_4.jfif", "Brahmaputra Valley Raw Cotton Trousers", "pants", "bottom", "Assam Handloom", ["Natural Ecru"], 1),
            ("item_5.jfif", "Kaziranga Forest Tribal Motif Woven Jacket", "jacket", "outerwear", "Assam Handloom", ["Fern Green"], 3),
            ("item_6.jfif", "Pat Silk Hand-Embroidered Pleated Skirt", "skirt", "bottom", "Assam Handloom", ["Midnight Indigo"], 2),
            ("item_7.jfif", "Majuli Island Riverine Linen Smock Top", "top", "top", "Assam Handloom", ["Sky Blue"], 1),
            ("item_8.jfif", "Tea Garden Emerald Silk Evening Dress", "dress", "onepiece", "Assam Handloom", ["Tea Emerald"], 2),
            ("item_9.jfif", "Sualkuchi Silk Weavers Handcrafted Shrug", "shrug", "outerwear", "Assam Handloom", ["Champagne Gold"], 2),
            ("item_10.jfif", "Haflong Hill Station Flannel Trousers", "pants", "bottom", "Assam Handloom", ["Slate Grey"], 3),
            ("item_11.jfif", "Bodo Tribal Geometric Tailored Blazer", "jacket", "outerwear", "Assam Handloom", ["Mustard Ochre"], 3),
            ("item_12.jfif", "Mishing Weave Patterned Cotton Tunic", "top", "top", "Assam Handloom", ["Crimson & Black"], 1),
            ("item_13.jfif", "Karbi Anglong Tribal Woven Midi Skirt", "skirt", "bottom", "Assam Handloom", ["Earthy Brown"], 2),
            ("item_14.jfif", "Guwahati Twilight Silk Wrap Maxi Dress", "dress", "onepiece", "Assam Handloom", ["Royal Purple"], 2),
            ("item_15.jfif", "Rhino Motif Organic Khadi Blouse", "top", "top", "Assam Handloom", ["Olive"], 1),
            ("item_16.jfif", "Assam Valley Relaxed Straight Pants", "pants", "bottom", "Assam Handloom", ["Off-White"], 1),
            ("item_17.jfif", "Winter Fog Eri Silk Padded Vest", "jacket", "outerwear", "Assam Handloom", ["Charcoal"], 3),
            ("item_18.jfif", "Kamakhya Temple Lotus Silk Cami", "top", "top", "Assam Handloom", ["Lotus Pink"], 1),
            ("item_19.jfif", "Bihu Celebration Golden Silk Gown", "dress", "onepiece", "Assam Handloom", ["Gold & Coral"], 2),
            ("item_20.jfif", "Eri Silk Lightweight Open Knit Shrug", "shrug", "outerwear", "Assam Handloom", ["Natural Oat"], 2),
        ]
    },
    # 10. GOA
    {
        "id": 10,
        "name": "Kiara Fernandes",
        "username": "kiara_fernandes",
        "role": "Coastal Architect & Heritage Restorer (Panaji & Margao)",
        "style_persona": "Goan Kunbi Weaves & Portuguese-Colonial Resort Chic",
        "preferred_colors": ["Kunbi Red & White Check", "Terracotta", "Seafoam Green", "Sunlit Linen", "Navy"],
        "temp_pref": "Warm / Coastal",
        "bio": "Traditional Kunbi checkered cotton sundresses, breezy linen pants, handcrafted crochet shrugs, and relaxed Indo-Portuguese coastal elegance.",
        "badge": "GOA · KUNBI WEAVES",
        "color": (255, 127, 80),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Kunbi Handloom Checkered Heritage Sundress", "dress", "onepiece", "Goan Coastal", ["Kunbi Red & White"], 1),
            ("item_2.jfif", "Fontainhas Latin Quarter Floral Slip Dress", "dress", "onepiece", "Goan Coastal", ["Terracotta Gold"], 1),
            ("item_3.jfif", "Panaji Mandovi River Linen Tunic Top", "top", "top", "Goan Coastal", ["Seafoam Green"], 1),
            ("item_4.jfif", "Palolem Beach Breezy Linen Drawstring Pants", "pants", "bottom", "Goan Coastal", ["Sunlit Linen"], 1),
            ("item_5.jfif", "Portuguese Heritage Embroidered Linen Blazer", "jacket", "outerwear", "Goan Coastal", ["Navy Blue"], 2),
            ("item_6.jfif", "Miramar Sunset High-Waist Pleated Skirt", "skirt", "bottom", "Goan Coastal", ["Coral Sunset"], 1),
            ("item_7.jfif", "Anjuna Artisanal Bohemian Cotton Halter Top", "top", "top", "Goan Coastal", ["White Crochet"], 1),
            ("item_8.jfif", "Cabo de Rama Cliffside Silk Evening Dress", "dress", "onepiece", "Goan Coastal", ["Deep Ocean Blue"], 2),
            ("item_9.jfif", "Goan Hand-Crocheted Open Lace Shrug", "shrug", "outerwear", "Goan Coastal", ["Sand Cream"], 1),
            ("item_10.jfif", "Calangute Tailored Coastal White Chinos", "pants", "bottom", "Goan Coastal", ["Pure White"], 1),
            ("item_11.jfif", "Old Goa Baroque Velvet Evening Bolero", "jacket", "outerwear", "Goan Coastal", ["Bordeaux Red"], 3),
            ("item_12.jfif", "Chapora Fort Breeze Linen Poplin Shirt", "top", "top", "Goan Coastal", ["Sage Green"], 1),
            ("item_13.jfif", "Vagator Coconut Palm Tiered Midi Skirt", "skirt", "bottom", "Goan Coastal", ["Teal Floral"], 1),
            ("item_14.jfif", "Mandrem Beachfront Organic Silk Day Dress", "dress", "onepiece", "Goan Coastal", ["Pale Lemon"], 1),
            ("item_15.jfif", "Saligao Village Embroidered Peasant Top", "top", "top", "Goan Coastal", ["Ivory & Coral"], 1),
            ("item_16.jfif", "Reis Magos Coastal Sailor Wide Trousers", "pants", "bottom", "Goan Coastal", ["Navy Stripe"], 1),
            ("item_17.jfif", "Monsoon Sea Spray Lightweight Windcheater", "jacket", "outerwear", "Goan Coastal", ["Aqua Green"], 2),
            ("item_18.jfif", "Goan Spice Plantation Breathable Camisole", "top", "top", "Goan Coastal", ["Mustard Ochre"], 1),
            ("item_19.jfif", "Dona Paula Moonlit Romance Silk Gown", "dress", "onepiece", "Goan Coastal", ["Midnight Teal"], 2),
            ("item_20.jfif", "Breezy Cotton Voile Resort Shrug", "shrug", "outerwear", "Goan Coastal", ["Sea Breeze White"], 1),
        ]
    },
    # 11. LUCKNOW & AWADH
    {
        "id": 11,
        "name": "Ayesha Siddiqui",
        "username": "ayesha_siddiqui",
        "role": "Awadhi Royal Couturier & Calligrapher (Lucknow)",
        "style_persona": "Lucknowi Chikankari & Mukaish Royal Subtlety",
        "preferred_colors": ["Powder Peach", "Mint Green", "Pure Pearl White", "Ice Blue", "Pale Lavender"],
        "temp_pref": "Moderate / Subtropical",
        "bio": "Delicate hand-shadow Chikankari kurtas, gossamer georgette Anarkalis with genuine silver Mukaish work, Awadhi Ghararas, and royal courtly grace.",
        "badge": "LUCKNOW · CHIKANKARI",
        "color": (255, 182, 193),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Lucknowi Shadow-Work Chikankari Anarkali Dress", "dress", "onepiece", "Awadhi Royal", ["Pearl White"], 1),
            ("item_2.jfif", "Silver Mukaish Work Pastel Georgette Gown", "dress", "onepiece", "Awadhi Royal", ["Powder Peach"], 2),
            ("item_3.jfif", "Hazratganj Fine Bakhiya Chikankari Kurta", "top", "top", "Awadhi Royal", ["Ice Blue"], 1),
            ("item_4.jfif", "Royal Awadhi Flared Georgette Gharara Pants", "pants", "bottom", "Awadhi Royal", ["Pale Lavender"], 2),
            ("item_5.jfif", "Bara Imambara Velvet Embroidered Court Jacket", "jacket", "outerwear", "Awadhi Royal", ["Royal Emerald"], 3),
            ("item_6.jfif", "Chanderi Zari Border Flared Evening Skirt", "skirt", "bottom", "Awadhi Royal", ["Silver Ivory"], 2),
            ("item_7.jfif", "Rumi Darwaza Hand-Embroidered Peplum Top", "top", "top", "Awadhi Royal", ["Mint Green"], 1),
            ("item_8.jfif", "Nawabi Court Organza Silk Festive Dress", "dress", "onepiece", "Awadhi Royal", ["Champagne Gold"], 2),
            ("item_9.jfif", "Delicate Chikankari Open-Front Summer Shrug", "shrug", "outerwear", "Awadhi Royal", ["Pure White"], 1),
            ("item_10.jfif", "Gomti River Cotton Straight-Cut Trousers", "pants", "bottom", "Awadhi Royal", ["Soft Beige"], 1),
            ("item_11.jfif", "Tepchi Stitch Structured Silk Evening Blazer", "jacket", "outerwear", "Awadhi Royal", ["Powder Blue"], 3),
            ("item_12.jfif", "Qaiserbagh Rose Petal Georgette Kurti", "top", "top", "Awadhi Royal", ["Rose Dust"], 1),
            ("item_13.jfif", "Zardozi Hand-Finished Pleated Midi Skirt", "skirt", "bottom", "Awadhi Royal", ["Ivory & Gold"], 2),
            ("item_14.jfif", "Chowk Heritage Pure Silk Jamdani Dress", "dress", "onepiece", "Awadhi Royal", ["Pale Turquoise"], 2),
            ("item_15.jfif", "Jaali Work Gossamer Cotton Tunic Top", "top", "top", "Awadhi Royal", ["Alabaster White"], 1),
            ("item_16.jfif", "Awadhi Royal Silk Cigarette Pants", "pants", "bottom", "Awadhi Royal", ["Silver Slate"], 2),
            ("item_17.jfif", "Winter Brocade Quilted Nehru Jacket", "jacket", "outerwear", "Awadhi Royal", ["Deep Plum"], 3),
            ("item_18.jfif", "Kundan Pearl Border Silk Camisole", "top", "top", "Awadhi Royal", ["Cream Pearl"], 1),
            ("item_19.jfif", "Wajid Ali Shah Twilight Velvet Gown Dress", "dress", "onepiece", "Awadhi Royal", ["Midnight Noir"], 3),
            ("item_20.jfif", "Chikankari Hand-Loomed Draped Shrug", "shrug", "outerwear", "Awadhi Royal", ["Soft Peach"], 1),
        ]
    },
    # 12. HYDERABAD & TELANGANA
    {
        "id": 12,
        "name": "Sahithi Reddy",
        "username": "sahithi_reddy",
        "role": "Fintech Director & Pearl Collector (Hyderabad)",
        "style_persona": "Pochampally Ikat & Royal Deccani Silk",
        "preferred_colors": ["Hyderabadi Maroon", "Pearl White", "Ikat Monochrome", "Deep Teal", "Charminar Gold"],
        "temp_pref": "Warm / Plateau",
        "bio": "Geometric Pochampally Ikat silk dresses, Gadwal temple border tunics, Hyderabadi pearl-embroidered jackets, and sleek Deccani power dressing.",
        "badge": "HYDERABAD · IKAT",
        "color": (0, 128, 128),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Pochampally Ikat Geometric Silk Gown Dress", "dress", "onepiece", "Deccani Royal", ["Ikat Monochrome"], 2),
            ("item_2.jfif", "Gadwal Gold Zari Temple Border Silk Dress", "dress", "onepiece", "Deccani Royal", ["Hyderabadi Maroon"], 2),
            ("item_3.jfif", "Charminar Pearl-Embroidered Tunic Top", "top", "top", "Deccani Royal", ["Pearl White"], 1),
            ("item_4.jfif", "HITEC City Tailored Pleated Linen Slacks", "pants", "bottom", "Deccani Royal", ["Slate Navy"], 1),
            ("item_5.jfif", "Nizam Royal Velvet Pearl-Embellished Koti", "jacket", "outerwear", "Deccani Royal", ["Deep Teal"], 3),
            ("item_6.jfif", "Narayanpet Handloom Cotton Pleated Skirt", "skirt", "bottom", "Deccani Royal", ["Charminar Gold"], 1),
            ("item_7.jfif", "Golkonda Diamond-Check Handloom Kurta", "top", "top", "Deccani Royal", ["Crimson & Black"], 2),
            ("item_8.jfif", "Jubilee Hills Rooftop Silk Slip Evening Dress", "dress", "onepiece", "Deccani Royal", ["Emerald Teal"], 2),
            ("item_9.jfif", "Telangana Handwoven Ikat Open Shrug", "shrug", "outerwear", "Deccani Royal", ["Black & White Ikat"], 2),
            ("item_10.jfif", "Banjara Hills Tailored Cotton Cigarette Pants", "pants", "bottom", "Deccani Royal", ["Off-White"], 1),
            ("item_11.jfif", "Deccan Corporate Bespoke Structured Blazer", "jacket", "outerwear", "Deccani Royal", ["Midnight Blue"], 3),
            ("item_12.jfif", "Warangal Durrie Pattern Modern Blouse", "top", "top", "Deccani Royal", ["Mustard Ochre"], 1),
            ("item_13.jfif", "Khada Dupatta Inspired Flared Silk Skirt", "skirt", "bottom", "Deccani Royal", ["Ruby Red"], 2),
            ("item_14.jfif", "Hussain Sagar Breeze Handloom Day Dress", "dress", "onepiece", "Deccani Royal", ["Turquoise"], 1),
            ("item_15.jfif", "Chowmahalla Palace Brocade Peplum Top", "top", "top", "Deccani Royal", ["Antique Gold"], 2),
            ("item_16.jfif", "Secunderabad Club Classic Chino Trousers", "pants", "bottom", "Deccani Royal", ["Beige Khaki"], 1),
            ("item_17.jfif", "Deccan Winter Quilted Velvet Evening Coat", "jacket", "outerwear", "Deccani Royal", ["Wine Red"], 3),
            ("item_18.jfif", "Basra Pearl Finished Silk Camisole", "top", "top", "Deccani Royal", ["Lustrous Ivory"], 1),
            ("item_19.jfif", "Falaknuma Palace Grand Silk Gala Dress", "dress", "onepiece", "Deccani Royal", ["Royal Navy & Gold"], 3),
            ("item_20.jfif", "Handspun Tussar Silk Lightweight Shrug", "shrug", "outerwear", "Deccani Royal", ["Natural Beige"], 1),
        ]
    },
    # 13. HIMACHAL PRADESH
    {
        "id": 13,
        "name": "Tanya Sharma",
        "username": "tanya_sharma",
        "role": "High-Altitude Naturalist & Ski Instructor (Manali & Shimla)",
        "style_persona": "Kullu Geometric Woolens & Himalayan Alpine Warmth",
        "preferred_colors": ["Heather Grey", "Pine Green", "Himalayan Berry", "Kullu Pattern Multi", "Oat"],
        "temp_pref": "Cold / Alpine",
        "bio": "Kullu woven geometric border woolen coats, Pattu handspun wool smocks, Pahadi embroidered vests, and mountain-weather layered fashion.",
        "badge": "HIMACHAL · KULLU",
        "color": (46, 139, 87),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Kullu Hand-Woven Geometric Border Wool Dress", "dress", "onepiece", "Himachali Alpine", ["Heather Grey & Multi"], 4),
            ("item_2.jfif", "Spiti Valley Yak Wool Knit Wrap Dress", "dress", "onepiece", "Himachali Alpine", ["Charcoal Oat"], 4),
            ("item_3.jfif", "Manali Alpine Cable Knit Woolen Sweater", "top", "top", "Himachali Alpine", ["Pine Green"], 3),
            ("item_4.jfif", "Rohtang Pass Thermal Weatherproof Trousers", "pants", "bottom", "Himachali Alpine", ["Slate Black"], 4),
            ("item_5.jfif", "Pahadi Hand-Embroidered Traditional Wool Vest", "jacket", "outerwear", "Himachali Alpine", ["Himalayan Berry"], 4),
            ("item_6.jfif", "Kinnauri Geometric Patterned Midi Skirt", "skirt", "bottom", "Himachali Alpine", ["Kullu Motif Black"], 3),
            ("item_7.jfif", "Shimla Ridge British-Heritage Flannel Shirt", "top", "top", "Himachali Alpine", ["Red Tartan"], 2),
            ("item_8.jfif", "Solang Valley Aprs-Ski Velvet Day Dress", "dress", "onepiece", "Himachali Alpine", ["Deep Burgundy"], 3),
            ("item_9.jfif", "Pattu Handspun Pure Wool Cardigan Shrug", "shrug", "outerwear", "Himachali Alpine", ["Natural Oat"], 4),
            ("item_10.jfif", "Dharamshala Mountain Trail Fleece Slacks", "pants", "bottom", "Himachali Alpine", ["Dark Olive"], 3),
            ("item_11.jfif", "Himalayan Heavy-Duty Down Winter Parka", "jacket", "outerwear", "Himachali Alpine", ["Mustard Yellow"], 5),
            ("item_12.jfif", "Chamba Rumal Floral Embroidered Blouse", "top", "top", "Himachali Alpine", ["Snow White"], 2),
            ("item_13.jfif", "Parvati Valley Hand-Knit Wool Skirt", "skirt", "bottom", "Himachali Alpine", ["Forest Green"], 3),
            ("item_14.jfif", "Kaza Starlight Heavy Cashmere Knit Dress", "dress", "onepiece", "Himachali Alpine", ["Midnight Navy"], 4),
            ("item_15.jfif", "Apple Orchard Harvest Merino Wool Kurti", "top", "top", "Himachali Alpine", ["Apple Red"], 3),
            ("item_16.jfif", "Kangra Valley Tailored Warm Woolen Pants", "pants", "bottom", "Himachali Alpine", ["Charcoal"], 3),
            ("item_17.jfif", "Bir Billing Wind-Shield Technical Jacket", "jacket", "outerwear", "Himachali Alpine", ["Teal Blue"], 4),
            ("item_18.jfif", "Cedar Forest Soft Cashmere Camisole Top", "top", "top", "Himachali Alpine", ["Cream"], 2),
            ("item_19.jfif", "Naggar Castle Heritage Woolen Gala Dress", "dress", "onepiece", "Himachali Alpine", ["Wine Wool"], 4),
            ("item_20.jfif", "Kullu Shawl Draped Open Poncho Shrug", "shrug", "outerwear", "Himachali Alpine", ["Grey & Red Kullu"], 4),
        ]
    },
    # 14. ODISHA
    {
        "id": 14,
        "name": "Shreya Mohapatra",
        "username": "shreya_mohapatra",
        "role": "Archaeological Conservator (Bhubaneswar & Puri)",
        "style_persona": "Sambalpuri Ikat & Temple Sculpture Splendor",
        "preferred_colors": ["Pasapalli Black & White", "Temple Terracotta", "Khandua Red", "Mustard Ochre", "Olive"],
        "temp_pref": "Moderate / Coastal",
        "bio": "Geometric Pasapalli check dresses, Sambalpuri Ikat tie-dye kurtas, Bomkai silk jackets, and centuries of Jagannath temple handloom heritage.",
        "badge": "ODISHA · SAMBALPURI",
        "color": (205, 92, 92),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Pasapalli Chessboard Ikat Silk Gown Dress", "dress", "onepiece", "Odisha Temple Heritage", ["Black & White Pasapalli"], 2),
            ("item_2.jfif", "Sambalpuri Bandha Tie-Dye Handloom Dress", "dress", "onepiece", "Odisha Temple Heritage", ["Khandua Red"], 2),
            ("item_3.jfif", "Konark Sun Temple Wheel Motif Kurti Top", "top", "top", "Odisha Temple Heritage", ["Temple Terracotta"], 1),
            ("item_4.jfif", "Puri Coastal Breathable Handloom Cotton Pants", "pants", "bottom", "Odisha Temple Heritage", ["Natural Sand"], 1),
            ("item_5.jfif", "Bomkai Silk Brocade Structured Koti Jacket", "jacket", "outerwear", "Odisha Temple Heritage", ["Mustard Ochre"], 3),
            ("item_6.jfif", "Kotpad Vegetable Dye Pleated Midi Skirt", "skirt", "bottom", "Odisha Temple Heritage", ["Madder Red & Coffee"], 2),
            ("item_7.jfif", "Bhubaneswar Heritage Ikkat Peplum Top", "top", "top", "Odisha Temple Heritage", ["Olive Green"], 1),
            ("item_8.jfif", "Chilika Lake Seagull Motif Silk Slip Dress", "dress", "onepiece", "Odisha Temple Heritage", ["Sky Indigo"], 1),
            ("item_9.jfif", "Berhampuri Poda Kumbha Handwoven Shrug", "shrug", "outerwear", "Odisha Temple Heritage", ["Gold & Maroon"], 2),
            ("item_10.jfif", "Cuttack Silver Filigree Cotton Straight Pants", "pants", "bottom", "Odisha Temple Heritage", ["Pure White"], 1),
            ("item_11.jfif", "Dhauli Peace Pagoda Structured Linen Blazer", "jacket", "outerwear", "Odisha Temple Heritage", ["Stone Grey"], 2),
            ("item_12.jfif", "Gopalpur Beach Relaxed Poplin Tunic", "top", "top", "Odisha Temple Heritage", ["Aqua Mint"], 1),
            ("item_13.jfif", "Pattachitra Painted Border Gathered Skirt", "skirt", "bottom", "Odisha Temple Heritage", ["Black & Crimson"], 2),
            ("item_14.jfif", "Jagannath Gita Govinda Calligraphy Dress", "dress", "onepiece", "Odisha Temple Heritage", ["Parchment Cream"], 2),
            ("item_15.jfif", "Simlipal Tiger Reserve Khadi Blouse Top", "top", "top", "Odisha Temple Heritage", ["Earthy Rust"], 1),
            ("item_16.jfif", "Odisha Artisan Handloom Relaxed Salwar", "pants", "bottom", "Odisha Temple Heritage", ["Charcoal"], 1),
            ("item_17.jfif", "Daringbadi Hill Station Winter Woolen Coat", "jacket", "outerwear", "Odisha Temple Heritage", ["Forest Green"], 3),
            ("item_18.jfif", "Silver Filigree Inspired Metallic Camisole", "top", "top", "Odisha Temple Heritage", ["Shimmer Silver"], 1),
            ("item_19.jfif", "Mukteshwar Temple Carved Stone Evening Dress", "dress", "onepiece", "Odisha Temple Heritage", ["Bronze Silk"], 2),
            ("item_20.jfif", "Sambalpuri Ikat Open Handloom Shrug", "shrug", "outerwear", "Odisha Temple Heritage", ["Red & Black Bandha"], 2),
        ]
    },
    # 15. LONDON, UK
    {
        "id": 15,
        "name": "Emma Watson",
        "username": "emma_watson",
        "role": "Fashion Editor & Stylist (London)",
        "style_persona": "British Heritage, Tartan & Savile Row Chic",
        "preferred_colors": ["Camel Gabardine", "Westminster Navy", "Crimson Tartan", "Cream Cashmere", "Charcoal"],
        "temp_pref": "Cool / Maritime",
        "bio": "Classic Mayfair trench dresses, Westminster pleated wool tartan midi skirts, Covent Garden cashmere knits, and Savile Row structured tailoring.",
        "badge": "LONDON · SAVILE ROW",
        "color": (25, 25, 112),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Mayfair Heritage Gabardine Trench Dress", "dress", "onepiece", "British Chic", ["Camel Tan"], 3),
            ("item_2.jfif", "Savile Row Double-Breasted Tailored Blazer", "jacket", "outerwear", "British Chic", ["Westminster Navy"], 3),
            ("item_3.jfif", "Chelsea Morning Ribbed Wool Knit Sweater", "top", "top", "British Chic", ["Cream Ivory"], 3),
            ("item_4.jfif", "Westminster Pleated Wool Tartan Midi Skirt", "skirt", "bottom", "British Chic", ["Navy & Crimson"], 3),
            ("item_5.jfif", "Bond Street Silk Slip Evening Dress", "dress", "onepiece", "British Chic", ["Emerald Silk"], 1),
            ("item_6.jfif", "Kensington High-Rise Flannel Tailored Trousers", "pants", "bottom", "British Chic", ["Dark Charcoal"], 3),
            ("item_7.jfif", "Notting Hill Pastel Cashmere Crewneck Top", "top", "top", "British Chic", ["Powder Blue"], 2),
            ("item_8.jfif", "Covent Garden Floral Silk Wrap Dress", "dress", "onepiece", "British Chic", ["Rose & Sage"], 2),
            ("item_9.jfif", "Piccadilly Cropped Merino Wool Shrug", "shrug", "outerwear", "British Chic", ["Charcoal Melange"], 2),
            ("item_10.jfif", "Soho Contemporary Tailored Pleated Chinos", "pants", "bottom", "British Chic", ["Olive Khaki"], 2),
            ("item_11.jfif", "Regent Street Heavy Herringbone Wool Coat", "jacket", "outerwear", "British Chic", ["Herringbone Grey"], 4),
            ("item_12.jfif", "Knightsbridge Poplin Crisp Collar Shirt", "top", "top", "British Chic", ["Oxford Blue"], 1),
            ("item_13.jfif", "Marylebone Classic Wool A-Line Skirt", "skirt", "bottom", "British Chic", ["Camel Wool"], 2),
            ("item_14.jfif", "Hyde Park Autumn Cable Knit Day Dress", "dress", "onepiece", "British Chic", ["Forest Green"], 3),
            ("item_15.jfif", "Belgravia Silk Blend Button-Down Blouse", "top", "top", "British Chic", ["Champagne"], 1),
            ("item_16.jfif", "Shoreditch Raw Denim Straight-Leg Slacks", "pants", "bottom", "British Chic", ["Dark Indigo"], 2),
            ("item_17.jfif", "St. James Velvet Cocktail Day Dress", "dress", "onepiece", "British Chic", ["Burgundy Velvet"], 3),
            ("item_18.jfif", "Trafalgar Rainproof Heavy Utility Parka", "jacket", "outerwear", "British Chic", ["Classic Navy"], 4),
            ("item_19.jfif", "Mayfair Mulberry Silk Evening Slip Dress", "dress", "onepiece", "British Chic", ["Midnight Black"], 2),
            ("item_20.jfif", "Thames Morning Merino Cardigan Shrug", "shrug", "outerwear", "British Chic", ["Oatmeal Heather"], 2),
        ]
    },
    # 16. PARIS, FRANCE
    {
        "id": 16,
        "name": "Camille Laurent",
        "username": "camille_laurent",
        "role": "Haute Couture Producer (Paris)",
        "style_persona": "Parisian Effortless Chic & Boucl Tweed",
        "preferred_colors": ["Ivory White", "Midnight Noir", "Boucl Tweed Navy", "Bordeaux Red", "Champagne"],
        "temp_pref": "Moderate / Oceanic",
        "bio": "Saint-Germain silk slip dresses, Rue Cambon boucl tweed jackets, Le Marais effortless denim, and Place Vendme timeless elegance.",
        "badge": "PARIS · HAUTE COUTURE",
        "color": (0, 0, 128),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Saint-Germain Bias-Cut Silk Slip Dress", "dress", "onepiece", "Parisian Chic", ["Midnight Noir"], 1),
            ("item_2.jfif", "Rue Cambon Classic Boucl Tweed Jacket", "jacket", "outerwear", "Parisian Chic", ["Ivory & Black"], 3),
            ("item_3.jfif", "Montmartre Breton Striped Boatneck Top", "top", "top", "Parisian Chic", ["Navy & White"], 1),
            ("item_4.jfif", "Le Marais Effortless High-Waist Denim Slacks", "pants", "bottom", "Parisian Chic", ["Washed Indigo"], 2),
            ("item_5.jfif", "Place Vendme Velvet Evening Gala Gown", "dress", "onepiece", "Parisian Chic", ["Bordeaux Red"], 3),
            ("item_6.jfif", "Palais Royal Pleated Flared Midi Skirt", "skirt", "bottom", "Parisian Chic", ["Noir Black"], 2),
            ("item_7.jfif", "Champs-lyses Silk Charmeuse Camisole Blouse", "top", "top", "Parisian Chic", ["Champagne"], 1),
            ("item_8.jfif", "Tuileries Garden Tiered Floral Chiffon Dress", "dress", "onepiece", "Parisian Chic", ["French Floral"], 1),
            ("item_9.jfif", "Seine Riverbank Cashmere Open Cardigan Shrug", "shrug", "outerwear", "Parisian Chic", ["Heather Grey"], 2),
            ("item_10.jfif", "Bastille Tailored Cigarette Ankle Trousers", "pants", "bottom", "Parisian Chic", ["Smoky Charcoal"], 2),
            ("item_11.jfif", "Haussmann Double-Breasted Woolen Trench Coat", "jacket", "outerwear", "Parisian Chic", ["Taupe Wool"], 4),
            ("item_12.jfif", "Caf de Flore Relaxed Poplin White Shirt", "top", "top", "Parisian Chic", ["Crisp White"], 1),
            ("item_13.jfif", "Latin Quarter High-Waist Buttoned Skirt", "skirt", "bottom", "Parisian Chic", ["Houndstooth"], 2),
            ("item_14.jfif", "Opra Garnier Dramatic Satin Cocktail Dress", "dress", "onepiece", "Parisian Chic", ["Emerald Green"], 2),
            ("item_15.jfif", "Rive Gauche Fine Gauge Turtleneck Top", "top", "top", "Parisian Chic", ["Pure Black"], 2),
            ("item_16.jfif", "Louvre Museum Tailored Wide-Leg Flannel Pants", "pants", "bottom", "Parisian Chic", ["Slate Navy"], 3),
            ("item_17.jfif", "Pigalle Velvet Evening Bolero Jacket", "jacket", "outerwear", "Parisian Chic", ["Deep Plum"], 3),
            ("item_18.jfif", "Sorbonne Chic Ribbed Knit Top", "top", "top", "Parisian Chic", ["Cream Beige"], 2),
            ("item_19.jfif", "Versailles Palace Golden Jacquard Slip Dress", "dress", "onepiece", "Parisian Chic", ["Pale Gold"], 2),
            ("item_20.jfif", "Saint-Honor Cashmere Cropped Shrug", "shrug", "outerwear", "Parisian Chic", ["Soft Black"], 2),
        ]
    },
    # 17. TOKYO, JAPAN
    {
        "id": 17,
        "name": "Hana Tanaka",
        "username": "hana_tanaka",
        "role": "Architect & Minimalist Sculptor (Tokyo)",
        "style_persona": "Japanese Draping, Indigo & Contemporary Kimono Cuts",
        "preferred_colors": ["Aizome Indigo", "Charcoal Grey", "Cherry Blossom Pink", "Wabi-Sabi Cream", "Slate Black"],
        "temp_pref": "Moderate / Oceanic",
        "bio": "Kimono-inspired crossover wrap dresses, asymmetric Japanese denim tailoring, Ginza structured silks, and Shibuya monochrome layers with immaculate clean lines.",
        "badge": "TOKYO · AIZOME INDIGO",
        "color": (25, 25, 112),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Contemporary Kimono-Crossover Silk Wrap Dress", "dress", "onepiece", "Japanese Minimalist", ["Aizome Indigo"], 2),
            ("item_2.jfif", "Ginza Architectural Structured Wool Dress", "dress", "onepiece", "Japanese Minimalist", ["Slate Black"], 3),
            ("item_3.jfif", "Shibuya Asymmetric Draped Cotton Top", "top", "top", "Japanese Minimalist", ["Wabi-Sabi Cream"], 1),
            ("item_4.jfif", "Okayama Selvedge Raw Denim Wide Trousers", "pants", "bottom", "Japanese Minimalist", ["Deep Indigo"], 3),
            ("item_5.jfif", "Harajuku Dropped-Shoulder Tailored Haori Coat", "jacket", "outerwear", "Japanese Minimalist", ["Charcoal Grey"], 3),
            ("item_6.jfif", "Roppongi Origami Pleated Sculptural Midi Skirt", "skirt", "bottom", "Japanese Minimalist", ["Matte Black"], 2),
            ("item_7.jfif", "Omotesando Minimalist Crisp High-Neck Blouse", "top", "top", "Japanese Minimalist", ["Snow White"], 1),
            ("item_8.jfif", "Yukata-Inspired Indigo Breathable Cotton Dress", "dress", "onepiece", "Japanese Minimalist", ["Indigo Wave"], 1),
            ("item_9.jfif", "Kyoto Bamboo-Knit Minimalist Open Shrug", "shrug", "outerwear", "Japanese Minimalist", ["Pale Sand"], 2),
            ("item_10.jfif", "Aoyama Pleated Cropped Tailored Trousers", "pants", "bottom", "Japanese Minimalist", ["Stone Grey"], 2),
            ("item_11.jfif", "Modern Noragi Technical Layering Jacket", "jacket", "outerwear", "Japanese Minimalist", ["Dark Navy"], 3),
            ("item_12.jfif", "Cherry Blossom Subtle Tint Silk Cami Top", "top", "top", "Japanese Minimalist", ["Sakura Pink"], 1),
            ("item_13.jfif", "Wabi-Sabi Deconstructed Wrap Skirt", "skirt", "bottom", "Japanese Minimalist", ["Raw Ecru"], 2),
            ("item_14.jfif", "Shinjuku Skyline Evening Monochrome Maxi Gown", "dress", "onepiece", "Japanese Minimalist", ["Pitch Black"], 2),
            ("item_15.jfif", "Akihabara Tech-Wear Breathable Poplin Shirt", "top", "top", "Japanese Minimalist", ["Cool Grey"], 1),
            ("item_16.jfif", "Yanaka Artisan Relaxed Flannel Hakama Pants", "pants", "bottom", "Japanese Minimalist", ["Charcoal"], 3),
            ("item_17.jfif", "Hokkaido Mountain Thermal Wool Trench Coat", "jacket", "outerwear", "Japanese Minimalist", ["Olive Brown"], 4),
            ("item_18.jfif", "Traditional Kasuri Woven Cotton Blouse", "top", "top", "Japanese Minimalist", ["Indigo Pattern"], 2),
            ("item_19.jfif", "Edo Castle Antique Silk Cocktail Dress", "dress", "onepiece", "Japanese Minimalist", ["Dark Plum"], 2),
            ("item_20.jfif", "Minimalist Cocoon Silhouette Cardigan Shrug", "shrug", "outerwear", "Japanese Minimalist", ["Ink Black"], 2),
        ]
    },
    # 18. SEOUL, SOUTH KOREA
    {
        "id": 18,
        "name": "Ji-woo Park",
        "username": "jiwoo_park",
        "role": "Digital Media Producer & Trendsetter (Seoul)",
        "style_persona": "Modern Hanbok Fusion & K-Fashion Street Tailoring",
        "preferred_colors": ["Pastel Lilac", "Hanbok Salmon Pink", "Clean Beige", "Oversized Charcoal", "Crisp White"],
        "temp_pref": "Moderate / Continental",
        "bio": "Modern Hanbok fusion wrap dresses, Seongsu dropped-shoulder blazers, Hongdae street layers, and Gangnam clean minimalist silhouettes.",
        "badge": "SEOUL · MODERN HANBOK",
        "color": (219, 112, 147),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Modern Hanbok Fusion Chima Wrap Evening Dress", "dress", "onepiece", "K-Fashion Chic", ["Salmon Pink & White"], 2),
            ("item_2.jfif", "Seongsu Oversized Dropped-Shoulder Blazer", "jacket", "outerwear", "K-Fashion Chic", ["Oversized Charcoal"], 3),
            ("item_3.jfif", "Hongdae Street Layered Pastel Cropped Top", "top", "top", "K-Fashion Chic", ["Pastel Lilac"], 1),
            ("item_4.jfif", "Gangnam Minimalist Clean Wide-Leg Slacks", "pants", "bottom", "K-Fashion Chic", ["Clean Beige"], 2),
            ("item_5.jfif", "Dongdaemun Tech-Fabric Longline Trench Coat", "jacket", "outerwear", "K-Fashion Chic", ["Light Khaki"], 3),
            ("item_6.jfif", "A-Line High-Waist Pleated Schoolgirl Midi Skirt", "skirt", "bottom", "K-Fashion Chic", ["Charcoal Grey"], 2),
            ("item_7.jfif", "Itaewon Contemporary Relaxed Poplin Shirt", "top", "top", "K-Fashion Chic", ["Crisp White"], 1),
            ("item_8.jfif", "Han River Sunset Pastel Tiered Summer Dress", "dress", "onepiece", "K-Fashion Chic", ["Sky Blue Pastel"], 1),
            ("item_9.jfif", "Jeju Island Hand-Knit Chunky Open Shrug", "shrug", "outerwear", "K-Fashion Chic", ["Butter Cream"], 3),
            ("item_10.jfif", "Insadong Artisan Hanbok Linen Wide Trousers", "pants", "bottom", "K-Fashion Chic", ["Off-White Linen"], 1),
            ("item_11.jfif", "K-Idol Double-Breasted Short Crop Blazer", "jacket", "outerwear", "K-Fashion Chic", ["Pinstripe Navy"], 2),
            ("item_12.jfif", "Myeongdong Sweetheart Ribbed Knit Top", "top", "top", "K-Fashion Chic", ["Soft Coral"], 1),
            ("item_13.jfif", "Asymmetrical Tiered Chiffon Statement Skirt", "skirt", "bottom", "K-Fashion Chic", ["Lavender Mist"], 2),
            ("item_14.jfif", "Sinsa-dong Boulevard Cocktail Slip Dress", "dress", "onepiece", "K-Fashion Chic", ["Emerald Satin"], 2),
            ("item_15.jfif", "Seoul Fashion Week Deconstructed Blouse Top", "top", "top", "K-Fashion Chic", ["Oversized White"], 1),
            ("item_16.jfif", "Hongdae Underground Relaxed Baggy Cargo Slacks", "pants", "bottom", "K-Fashion Chic", ["Washed Olive"], 2),
            ("item_17.jfif", "Heavyweight Winter Puffer Down Coat", "jacket", "outerwear", "K-Fashion Chic", ["Glossy Black"], 5),
            ("item_18.jfif", "Delicate Silk Rib-Knit Square-Neck Top", "top", "top", "K-Fashion Chic", ["Pale Mint"], 1),
            ("item_19.jfif", "Gyeongbokgung Moonlit Palace Velvet Dress", "dress", "onepiece", "K-Fashion Chic", ["Midnight Plum"], 3),
            ("item_20.jfif", "Cropped Bolero Cardigan Knit Shrug", "shrug", "outerwear", "K-Fashion Chic", ["Oatmeal Heather"], 2),
        ]
    },
    # 19. NEW YORK, USA
    {
        "id": 19,
        "name": "Rachel Adams",
        "username": "rachel_adams",
        "role": "Corporate Executive & Art Collector (New York)",
        "style_persona": "Manhattan Power Minimalist & Soho Modern Glam",
        "preferred_colors": ["Wall Street Pinstripe", "Tribeca Camel", "Soho Onyx Black", "Cashmere Ivory", "Slate Grey"],
        "temp_pref": "Moderate / Continental",
        "bio": "Sharp Wall Street tailored suits, Tribeca cashmere coats, Soho rooftop cocktail slip dresses, and Hudson Yards modern minimalist staples.",
        "badge": "NEW YORK · MANHATTAN",
        "color": (47, 79, 79),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Wall Street Power Tailored Pinstripe Suit Dress", "dress", "onepiece", "Manhattan Minimalist", ["Pinstripe Charcoal"], 3),
            ("item_2.jfif", "Soho Rooftop Silk Satin Cocktail Slip Dress", "dress", "onepiece", "Manhattan Minimalist", ["Onyx Black"], 1),
            ("item_3.jfif", "Tribeca Double-Faced Cashmere Overcoat", "jacket", "outerwear", "Manhattan Minimalist", ["Tribeca Camel"], 4),
            ("item_4.jfif", "Madison Avenue High-Waist Wide Pleated Slacks", "pants", "bottom", "Manhattan Minimalist", ["Ivory Cream"], 2),
            ("item_5.jfif", "Hudson Yards Bespoke Double-Breasted Blazer", "jacket", "outerwear", "Manhattan Minimalist", ["Midnight Navy"], 3),
            ("item_6.jfif", "Fifth Avenue Leather Pencil Midi Skirt", "skirt", "bottom", "Manhattan Minimalist", ["Cognac Leather"], 3),
            ("item_7.jfif", "Central Park Morning Fine Silk Button-Down", "top", "top", "Manhattan Minimalist", ["Crisp White"], 1),
            ("item_8.jfif", "Met Gala Sculptural Asymmetric Evening Gown", "dress", "onepiece", "Manhattan Minimalist", ["Deep Emerald"], 2),
            ("item_9.jfif", "Chelsea Gallery Lightweight Wool Shrug", "shrug", "outerwear", "Manhattan Minimalist", ["Slate Grey"], 2),
            ("item_10.jfif", "Flatiron District Tailored Cigarette Chinos", "pants", "bottom", "Manhattan Minimalist", ["Black Onyx"], 2),
            ("item_11.jfif", "Brooklyn Heights Vintage Leather Moto Jacket", "jacket", "outerwear", "Manhattan Minimalist", ["Washed Black"], 3),
            ("item_12.jfif", "Greenwich Village Fine Cashmere Turtleneck", "top", "top", "Manhattan Minimalist", ["Heather Oat"], 3),
            ("item_13.jfif", "DUMBO Waterfront Pleated Silk Maxi Skirt", "skirt", "bottom", "Manhattan Minimalist", ["Champagne Gold"], 2),
            ("item_14.jfif", "Upper East Side Classic Boucl Day Dress", "dress", "onepiece", "Manhattan Minimalist", ["Navy Tweed"], 3),
            ("item_15.jfif", "Bowery Relaxed Fit Linen Poplin Shirt", "top", "top", "Manhattan Minimalist", ["Sky Blue"], 1),
            ("item_16.jfif", "Meatpacking District Clean Raw Denim Jeans", "pants", "bottom", "Manhattan Minimalist", ["Dark Indigo"], 2),
            ("item_17.jfif", "Manhattan Blizzard Heavy Down Parka Coat", "jacket", "outerwear", "Manhattan Minimalist", ["Matte Black"], 5),
            ("item_18.jfif", "Gramercy Park Silk Rib-Knit Cami Top", "top", "top", "Manhattan Minimalist", ["Blush Taupe"], 1),
            ("item_19.jfif", "Lincoln Center Opera Velvet Evening Gown", "dress", "onepiece", "Manhattan Minimalist", ["Royal Ruby"], 3),
            ("item_20.jfif", "Soho Chic Cropped Cashmere Knit Shrug", "shrug", "outerwear", "Manhattan Minimalist", ["Jet Black"], 2),
        ]
    },
    # 20. MONACO & RIVIERA
    {
        "id": 20,
        "name": "Evelyn Robinson",
        "username": "evelyn_robinson",
        "role": "Yachting & Luxury Consultant (Monaco)",
        "style_persona": "Riviera Quiet Luxury & Resort Haute Glamour",
        "preferred_colors": ["Riviera Mediterranean Blue", "Yacht White", "Champagne Gold", "Linen Sand", "Coral Sunset"],
        "temp_pref": "Warm / Mediterranean",
        "bio": "Monte Carlo grand casino evening silks, Port Hercules yachting crisp linens, Cap d'Antibes breezy sundresses, and Cannes festival tailoring.",
        "badge": "MONACO · RIVIERA LUXE",
        "color": (70, 130, 180),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Monte Carlo Grand Casino Silk Slip Gown", "dress", "onepiece", "Riviera Luxe", ["Champagne Gold"], 1),
            ("item_2.jfif", "Port Hercules Yachting Crisp White Linen Dress", "dress", "onepiece", "Riviera Luxe", ["Yacht White"], 1),
            ("item_3.jfif", "Cap d'Antibes Breathable Raw Linen Tunic", "top", "top", "Riviera Luxe", ["Mediterranean Blue"], 1),
            ("item_4.jfif", "Saint-Tropez High-Waist Flowing Palazzo Pants", "pants", "bottom", "Riviera Luxe", ["Linen Sand"], 1),
            ("item_5.jfif", "Cannes Red Carpet Double-Breasted Silk Blazer", "jacket", "outerwear", "Riviera Luxe", ["Ivory White"], 2),
            ("item_6.jfif", "Htel de Paris Pleated Silk Resort Skirt", "skirt", "bottom", "Riviera Luxe", ["Coral Sunset"], 1),
            ("item_7.jfif", "Villefranche Breton Striped Silk Blend Top", "top", "top", "Riviera Luxe", ["Navy & White"], 1),
            ("item_8.jfif", "Larvotto Beachfront Silk Halter Day Dress", "dress", "onepiece", "Riviera Luxe", ["Emerald Green"], 1),
            ("item_9.jfif", "Cap Ferrat Hand-Knitted Open Silk Shrug", "shrug", "outerwear", "Riviera Luxe", ["Cream Gold"], 1),
            ("item_10.jfif", "Beaulieu-sur-Mer Tailored Summer Chinos", "pants", "bottom", "Riviera Luxe", ["Sand Beige"], 1),
            ("item_11.jfif", "Casino Square Velvet Evening Tuxedo Jacket", "jacket", "outerwear", "Riviera Luxe", ["Midnight Noir"], 3),
            ("item_12.jfif", "Menton Citrus Embroidered Cotton Blouse", "top", "top", "Riviera Luxe", ["Lemon Sorbet"], 1),
            ("item_13.jfif", "Eze Medieval Village High-Waist Pencil Skirt", "skirt", "bottom", "Riviera Luxe", ["Onyx Black"], 2),
            ("item_14.jfif", "French Riviera Sunset Chiffon Maxi Dress", "dress", "onepiece", "Riviera Luxe", ["Rose Gold"], 1),
            ("item_15.jfif", "Princess Grace Silk Camisole Blouse Top", "top", "top", "Riviera Luxe", ["Blush Pearl"], 1),
            ("item_16.jfif", "Antibes Coastal Pleated Silk Blend Slacks", "pants", "bottom", "Riviera Luxe", ["Navy Blue"], 2),
            ("item_17.jfif", "Saint-Paul-de-Vence Evening Cashmere Cardigan", "jacket", "outerwear", "Riviera Luxe", ["Heather Grey"], 2),
            ("item_18.jfif", "Nice Promenade Daily Cotton Ribbed Top", "top", "top", "Riviera Luxe", ["Crisp White"], 1),
            ("item_19.jfif", "Monaco Grand Gala Dramatic Velvet Gown", "dress", "onepiece", "Riviera Luxe", ["Royal Sapphire"], 3),
            ("item_20.jfif", "Riviera Coastal Evening Cashmere Shrug", "shrug", "outerwear", "Riviera Luxe", ["Champagne Cream"], 2),
        ]
    }
]

def migrate_database():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Loading category-matched fashion image pools...")
    cat_pools = load_category_image_pools()
    for k, v in cat_pools.items():
        print(f"  - Category '{k}': {len(v)} base templates")

    # Clean existing items for users 1 to 20
    cursor.execute("DELETE FROM wardrobe_items WHERE user_id BETWEEN 1 AND 20")
    conn.commit()

    total_items = 0

    OCCASION_PLANS = {
        "onepiece": [
            ["wedding", "formal"],
            ["wedding", "party"],
            ["date", "party"],
            ["travel", "casual", "college"],
            ["formal", "party", "date"],
            ["wedding", "formal", "party"],
        ],
        "top": [
            ["casual", "college", "wedding"],
            ["office", "formal"],
            ["college", "casual", "office"],
            ["travel", "casual", "workout"],
            ["workout", "casual"],
            ["date", "party"],
        ],
        "bottom": [
            ["casual", "college", "wedding"],
            ["office", "formal"],
            ["college", "date", "party"],
            ["travel", "casual", "office"],
            ["workout", "travel", "casual"],
            ["party", "date", "formal"],
        ],
        "outerwear": [
            ["wedding", "party", "formal"],
            ["office", "formal"],
            ["workout", "travel"],
            ["college", "date", "casual"],
            ["party", "date", "casual"],
        ],
    }

    for u_idx, u in enumerate(REGIONAL_USERS):
        uid = u["id"]
        user_dir = USER_WARDROBES_DIR / str(uid)
        user_dir.mkdir(exist_ok=True)

        # Update or Insert User Record
        cursor.execute("SELECT id FROM users WHERE id = ?", (uid,))
        exists = cursor.fetchone()
        colors_json = json.dumps(u["preferred_colors"])

        if exists:
            cursor.execute("""
                UPDATE users SET
                    name = ?,
                    username = ?,
                    role = ?,
                    style_persona = ?,
                    preferred_colors = ?,
                    temp_pref = ?,
                    bio = ?
                WHERE id = ?
            """, (u["name"], u["username"], u["role"], u["style_persona"], colors_json, u["temp_pref"], u["bio"], uid))
        else:
            from hashlib import sha256
            p_hash = sha256("pass123".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (id, name, username, password_hash, role, style_persona, preferred_colors, temp_pref, bio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, u["name"], u["username"], p_hash, u["role"], u["style_persona"], colors_json, u["temp_pref"], u["bio"]))

        print(f"Processing User {uid}: {u['name']} (@{u['username']}) - {u['badge']}")

        grp_counts = {"onepiece": 0, "top": 0, "bottom": 0, "outerwear": 0}
        cat_counts = {}

        # Count totals per group for this user so we know which is the last top/bottom
        total_tops = sum(1 for it in u["items"] if it[3] == "top")
        total_bottoms = sum(1 for it in u["items"] if it[3] == "bottom")

        for i_idx, item in enumerate(u["items"]):
            fname, iname, cat, grp, st, colors, warmth = item
            g_idx = grp_counts.get(grp, 0)
            grp_counts[grp] = g_idx + 1

            plan_list = OCCASION_PLANS.get(grp, [["casual", "college"]])
            item_occs = list(plan_list[g_idx % len(plan_list)])

            # Ensure if a user has exactly 5 tops, top #3 also covers date/party and top #4 covers workout
            if grp == "top" and total_tops == 5:
                if g_idx == 3:
                    item_occs = ["travel", "date", "party"]
                elif g_idx == 4:
                    item_occs = ["workout", "casual"]
            if grp == "bottom" and total_bottoms == 5 and g_idx == 4:
                item_occs = ["workout", "travel", "casual"]

            # Enrich workout item names so they clearly read as active/movement cultural wear
            if "workout" in item_occs and grp == "top" and g_idx == (4 if total_tops >= 5 else total_tops - 1):
                if not any(w in iname.lower() for w in ["active", "movement", "yoga", "sport", "breathable"]):
                    iname = f"{iname} (Active Movement Fit)"
            elif "workout" in item_occs and grp == "bottom" and g_idx == (4 if total_bottoms >= 5 else total_bottoms - 1):
                if not any(w in iname.lower() for w in ["active", "movement", "yoga", "jogger", "stretch"]):
                    iname = f"{iname} (Active Stretch Fit)"

            # Pick base image strictly from the matching garment category pool
            pool_key = cat if cat in cat_pools else ("dress" if grp == "onepiece" else ("pants" if grp == "bottom" else ("jacket" if grp == "outerwear" else "top")))
            pool = cat_pools[pool_key]
            c_idx = cat_counts.get(pool_key, 0)
            cat_counts[pool_key] = c_idx + 1
            base_img = pool[(u_idx * 3 + c_idx) % len(pool)]

            primary_occ = item_occs[0] if item_occs else "casual"
            styled_img = style_image(
                base_img=base_img,
                tag=f"{u['badge']} · {cat}",
                occ_label=primary_occ,
                color_rgb=u["color"],
                u_idx=u_idx,
                i_idx=i_idx,
                is_kerala=u["is_kerala"],
                is_punjab=u["is_punjab"],
            )
            dest_file = user_dir / fname
            styled_img.save(dest_file, "JPEG", quality=88)

            tags_json = json.dumps(item_occs)

            cursor.execute("""
                INSERT INTO wardrobe_items (user_id, filename, name, category, group_type, style, colors, warmth_level, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                fname,
                iname,
                cat,
                grp,
                st,
                json.dumps(colors),
                warmth,
                tags_json
            ))
            total_items += 1

    conn.commit()
    conn.close()
    print(f"\nSUCCESS! Seeded 20 distinct regional wardrobes with {total_items} items total.")


def provision_new_user_wardrobe(user_id: int, name: str, username: str, cursor) -> dict:
    """
    Fast provisioning of a complete 20-piece occasion-tagged wardrobe for a newly signed-up user.
    Covers all 9 occasions: casual, college, travel, office, formal, wedding, party, date, workout.
    """
    import shutil
    OCCASION_PLANS = {
        "onepiece": [
            ["wedding", "formal"],
            ["wedding", "party"],
            ["date", "party"],
            ["travel", "casual", "college"],
            ["formal", "party", "date"],
            ["wedding", "formal", "party"],
        ],
        "top": [
            ["casual", "college", "wedding"],
            ["office", "formal"],
            ["college", "casual", "office"],
            ["travel", "casual", "workout"],
            ["workout", "casual"],
            ["date", "party"],
        ],
        "bottom": [
            ["casual", "college", "wedding"],
            ["office", "formal"],
            ["college", "date", "party"],
            ["travel", "casual", "office"],
            ["workout", "travel", "casual"],
            ["party", "date", "formal"],
        ],
        "outerwear": [
            ["wedding", "party", "formal"],
            ["office", "formal"],
            ["workout", "travel"],
            ["college", "date", "casual"],
            ["party", "date", "casual"],
        ],
    }

    combined = f"{name} {username}".lower()
    chosen_template = None
    region_keywords = [
        (["punjab", "kaur", "singh", "patiala", "phulkari"], 0),
        (["kerala", "nair", "menon", "pillai", "kasavu", "kochi", "ukken", "thomas", "varghese", "kurian"], 1),
        (["rajasthan", "jaipur", "rathore", "mewar", "bandhani"], 2),
        (["bengal", "kolkata", "banerjee", "chatterjee", "mukherjee", "das"], 3),
        (["kashmir", "srinagar", "mir", "wani", "pheran"], 4),
        (["gujarat", "patel", "shah", "mehta", "patola", "kutch"], 5),
        (["tamil", "chennai", "sundaram", "iyer", "kanchi"], 6),
        (["maharashtra", "mumbai", "pune", "deshmukh", "kulkarni", "paithani"], 7),
        (["assam", "guwahati", "barua", "bora", "muga"], 8),
        (["goa", "fernandes", "dsouza", "pereira", "resort"], 9),
        (["lucknow", "awadh", "siddiqui", "khan", "chikankari"], 10),
        (["hyderabad", "reddy", "rao", "telangana", "ikkat"], 11),
        (["himachal", "sharma", "verma", "kullu", "shimla"], 12),
        (["odisha", "mohapatra", "patnaik", "sambalpuri"], 13),
        (["london", "british", "uk", "savile"], 14),
        (["paris", "french", "laurent"], 15),
        (["tokyo", "japan", "tanaka"], 16),
        (["seoul", "korea", "park", "kim", "lee"], 17),
        (["nyc", "new york", "manhattan", "streetwear"], 18),
        (["milan", "italian", "luxury"], 19),
    ]
    for kw_list, idx in region_keywords:
        if any(kw in combined for kw in kw_list):
            chosen_template = REGIONAL_USERS[idx]
            break

    if chosen_template is None:
        chosen_template = REGIONAL_USERS[(user_id - 1) % len(REGIONAL_USERS)]

    template_uid = chosen_template["id"]
    template_dir = USER_WARDROBES_DIR / str(template_uid)
    user_dir = USER_WARDROBES_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    cursor.execute("DELETE FROM wardrobe_items WHERE user_id = ?", (user_id,))

    grp_counts = {"onepiece": 0, "top": 0, "bottom": 0, "outerwear": 0}
    total_tops = sum(1 for it in chosen_template["items"] if it[3] == "top")
    total_bottoms = sum(1 for it in chosen_template["items"] if it[3] == "bottom")

    for item in chosen_template["items"]:
        fname, iname, cat, grp, st, colors, warmth = item
        g_idx = grp_counts.get(grp, 0)
        grp_counts[grp] = g_idx + 1

        plan_list = OCCASION_PLANS.get(grp, [["casual", "college"]])
        item_occs = list(plan_list[g_idx % len(plan_list)])

        if grp == "top" and total_tops == 5:
            if g_idx == 3:
                item_occs = ["travel", "date", "party"]
            elif g_idx == 4:
                item_occs = ["workout", "casual"]
        if grp == "bottom" and total_bottoms == 5 and g_idx == 4:
            item_occs = ["workout", "travel", "casual"]

        if "workout" in item_occs and grp == "top" and g_idx == (4 if total_tops >= 5 else total_tops - 1):
            if not any(w in iname.lower() for w in ["active", "movement", "yoga", "sport", "breathable"]):
                iname = f"{iname} (Active Movement Fit)"
        elif "workout" in item_occs and grp == "bottom" and g_idx == (4 if total_bottoms >= 5 else total_bottoms - 1):
            if not any(w in iname.lower() for w in ["active", "movement", "yoga", "jogger", "stretch"]):
                iname = f"{iname} (Active Stretch Fit)"

        src_file = template_dir / fname
        dest_file = user_dir / fname
        if src_file.exists():
            shutil.copy2(src_file, dest_file)

        cursor.execute("""
            INSERT INTO wardrobe_items (user_id, filename, name, category, group_type, style, colors, warmth_level, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            fname,
            iname,
            cat,
            grp,
            st,
            json.dumps(colors),
            warmth,
            json.dumps(item_occs)
        ))

    return chosen_template


if __name__ == "__main__":
    migrate_database()
