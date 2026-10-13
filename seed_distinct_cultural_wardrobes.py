import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "smart_wardrobe.db"
USER_WARDROBES_DIR = BASE_DIR / "user_wardrobes"
USER_WARDROBES_DIR.mkdir(exist_ok=True)
CACHE_DIR = BASE_DIR / ".image_cache"
CACHE_DIR.mkdir(exist_ok=True)
WARDROBE_DIR = BASE_DIR / "wardrobe"

def load_category_image_pools():
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
    centering_x = 0.25 + ((u_idx * 17 + i_idx * 11) % 50) / 100.0
    centering_y = 0.25 + ((u_idx * 13 + i_idx * 9) % 50) / 100.0
    img = ImageOps.fit(base_img, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(centering_x, centering_y))

    tint = Image.new("RGB", (target_w, target_h), color_rgb)
    img = Image.blend(img, tint, 0.08)
    draw = ImageDraw.Draw(img)

    if is_kerala:
        border_h = 44
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(218, 165, 32))
        draw.line([0, target_h - border_h - 4, target_w, target_h - border_h - 4], fill=(184, 134, 11), width=4)
        draw.line([0, target_h - border_h + 10, target_w, target_h - border_h + 10], fill=(255, 223, 0), width=2)
        overlay = Image.new("RGB", (target_w, target_h), (252, 248, 238))
        img = Image.blend(img, overlay, 0.12)
        draw = ImageDraw.Draw(img)
    elif is_punjab:
        border_h = 40
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(224, 17, 95))
        step = 25
        for x in range(0, target_w, step):
            draw.polygon([(x, target_h), (x + step // 2, target_h - border_h + 4), (x + step, target_h)], fill=(255, 191, 0))
        draw.line([0, target_h - border_h, target_w, target_h - border_h], fill=(0, 168, 107), width=3)
    else:
        border_h = 34
        draw.rectangle([0, target_h - border_h, target_w, target_h], fill=(22, 18, 16))
        draw.line([0, target_h - border_h, target_w, target_h - border_h], fill=color_rgb, width=4)
        for x in range(16, target_w - 16, 28):
            draw.ellipse([x, target_h - border_h + 12, x + 8, target_h - border_h + 20], fill=color_rgb)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    pill_w = min(target_w - 24, max(210, len(tag) * 7 + 44))
    pill_h = 30
    pill_x0, pill_y0 = 12, 12
    draw.rounded_rectangle([pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h], radius=6, fill=(18, 18, 22))
    draw.ellipse([pill_x0 + 8, pill_y0 + 9, pill_x0 + 20, pill_y0 + 21], fill=color_rgb)
    draw.text((pill_x0 + 26, pill_y0 + 9), tag.upper(), fill=(245, 245, 245), font=font)

    if occ_label:
        occ_text = occ_label.upper()
        occ_w = max(76, len(occ_text) * 7 + 22)
        ox0 = target_w - occ_w - 12
        oy0 = 12
        draw.rounded_rectangle([ox0, oy0, ox0 + occ_w, oy0 + 28], radius=14, fill=(122, 31, 43))
        draw.text((ox0 + 11, oy0 + 8), occ_text, fill=(255, 248, 240), font=font)

    return img


REGIONAL_USERS_10 = [
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
            ("item_1.jfif", "Amritsari Tilla & Resham Embroidered Chanderi Silk Anarkali Dress", "dress", "onepiece", "Punjabi Heritage", ["Rani Pink", "Gold"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Jalandhari Velvet Festive Cocktail Gown Dress", "dress", "onepiece", "Punjabi Heritage", ["Emerald Velvet"], 3, ["party", "date", "formal"]),
            ("item_3.jfif", "Baisakhi Sunlit Mustard Cotton Slip Day Dress", "dress", "onepiece", "Punjabi Heritage", ["Mustard Gold"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Chandigarh Poplin Embroidered Short Kurti Top", "top", "top", "Punjabi Heritage", ["Pastel Mint"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Ludhiana Tailored Raw Silk Mandarin Collar Tunic Top", "top", "top", "Punjabi Heritage", ["Deep Crimson"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Active Punjabi Stretch Cotton Movement Kurti Top", "top", "top", "Punjabi Heritage", ["Pure White"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Royal Patiala Pleated Georgette Heavy Salwar Trousers", "pants", "bottom", "Punjabi Heritage", ["Royal Blue"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Phulkari Geometric Threadwork Flared Gathered Skirt", "skirt", "bottom", "Punjabi Heritage", ["Multi Phulkari"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Velvet Giddha Heritage Embroidered Structured Koti Jacket", "jacket", "outerwear", "Punjabi Heritage", ["Wine Velvet"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Handcrafted Multicolor Resham Threadwork Open Shrug", "shrug", "outerwear", "Punjabi Heritage", ["Gold Shimmer"], 2, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Pure Kasavu 24K Gold Zari Bordered Tissue Saree Dress", "dress", "onepiece", "Kerala Kasavu", ["Off-White & Gold"], 1, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Royal Travancore Emerald Green Silk Evening Gown Dress", "dress", "onepiece", "Kerala Kasavu", ["Peacock Emerald"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Kovalam Beachside Breathable Organic Cotton Sundress", "dress", "onepiece", "Kerala Kasavu", ["Pure Cream"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Onam Festive Handloom Kasavu Temple Kurti Top", "top", "top", "Kerala Kasavu", ["Ivory Gold"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Ernakulam Crisp Cotton Formal High-Neck Peplum Blouse", "top", "top", "Kerala Kasavu", ["Temple Red"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Backwater Yoga & Movement Breathable Khadi Active Top", "top", "top", "Kerala Kasavu", ["Sky Blue"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Handwoven Cream Kasavu Silk-Cotton Tapered Slacks", "pants", "bottom", "Kerala Kasavu", ["Kasavu Gold"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Traditional Kasavu Zari Hemline Pleated Midi Skirt", "skirt", "bottom", "Kerala Kasavu", ["Off-White Gold"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Thrissur Golden Brocade Tailored Ethnic Crop Blazer", "jacket", "outerwear", "Kerala Kasavu", ["Gold Brocade"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Kumarakom Handspun Lotus White Fine Open Shrug", "shrug", "outerwear", "Kerala Kasavu", ["Lotus Pink Accent"], 1, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Jaipur Crimson Gota Patti Embellished Georgette Gown Dress", "dress", "onepiece", "Rajasthani Royal", ["Ruby Red"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Udaipur Lake Palace Twilight Silk Kaftan Evening Dress", "dress", "onepiece", "Rajasthani Royal", ["Emerald Teal"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Leheriya Wave-Printed Chiffon Tiered Day Dress", "dress", "onepiece", "Rajasthani Royal", ["Marigold Coral"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Sanganeri Indigo Floral Woodblock Poplin Kurti Top", "top", "top", "Rajasthani Royal", ["Indigo Blue"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Shekhawati Mirror-Loom Tailored Silk Peplum Blouse", "top", "top", "Rajasthani Royal", ["Saffron Gold"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Thar Desert Breathable Cotton Active Stretch Top", "top", "top", "Rajasthani Royal", ["Camel Sand"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Jodhpur Royal Silk Tailored Jodhpuri Riding Trousers", "pants", "bottom", "Rajasthani Royal", ["Sand Beige"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Barmer Mirror-Work Flared Chaniya Ethnic Skirt", "skirt", "bottom", "Rajasthani Royal", ["Turquoise Blue"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Mewari Royal Velvet Embroidered Festive Koti Jacket", "jacket", "outerwear", "Rajasthani Royal", ["Midnight Ruby"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Bandhej Fine Hand-Knotted Silk-Blend Layering Shrug", "shrug", "outerwear", "Rajasthani Royal", ["Sunset Rust"], 2, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Dhaka Jamdani Woven Floral Motif Scarlet Silk Saree Dress", "dress", "onepiece", "Bengal Heritage", ["Scarlet & Gold"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Bishnupur Terracotta Tone Pure Silk Evening Slip Dress", "dress", "onepiece", "Bengal Heritage", ["Terracotta Bronze"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Shantiniketan Batik Breathable Muslin Cotton Day Dress", "dress", "onepiece", "Bengal Heritage", ["Tussar Cream"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "College Street Kantha Needlework Tussar Silk Kurti Top", "top", "top", "Bengal Heritage", ["Natural Beige"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Calcutta Club Tailored Crisp Cotton Mandarin Blouse", "top", "top", "Bengal Heritage", ["Midnight Indigo"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Sundarbans Eco-Cotton Active Mobility Kurta Top", "top", "top", "Bengal Heritage", ["Forest Moss"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Tangail Weave Handloom Tailored Relaxed Chinos", "pants", "bottom", "Bengal Heritage", ["Charcoal Slate"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Lal-Paad White & Red Border Handloom Gathered Skirt", "skirt", "bottom", "Bengal Heritage", ["White & Crimson"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Swadeshi Indigo Dyed Khadi Tailored Nehru Blazer", "jacket", "outerwear", "Bengal Heritage", ["Indigo Blue"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Artisanal Kantha Multi-Thread Embroidered Open Shrug", "shrug", "outerwear", "Bengal Heritage", ["Multi Resham"], 2, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Srinagar Royal Velvet Gold Tilla Embroidered Pheran Dress", "dress", "onepiece", "Kashmiri Royal", ["Velvet Maroon"], 4, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Dal Lake Twilight Navy Silk-Velvet Evening Gown Dress", "dress", "onepiece", "Kashmiri Royal", ["Midnight Navy"], 3, ["party", "date", "formal"]),
            ("item_3.jfif", "Gulmarg Snow Cashmere Woolen Wrap Midi Day Dress", "dress", "onepiece", "Kashmiri Royal", ["Snow Cream"], 3, ["casual", "travel", "college"]),
            ("item_4.jfif", "Aari Needlework Chinar Leaf Patterned Fine Wool Kurti Top", "top", "top", "Kashmiri Royal", ["Chinar Rust"], 2, ["casual", "college", "office"]),
            ("item_5.jfif", "Pashmina Silk-Wool Blend Formal High-Collar Blouse", "top", "top", "Kashmiri Royal", ["Saffron Gold"], 3, ["office", "formal", "date"]),
            ("item_6.jfif", "Himalayan Alpine Thermal Fleece Movement Active Top", "top", "top", "Kashmiri Royal", ["Slate Black"], 3, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Pahalgam Heavy Tweed Tailored Pleated Woolen Trousers", "pants", "bottom", "Kashmiri Royal", ["Charcoal Wool"], 4, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Kashmiri Tartan Wool Warm Gathered Midi Skirt", "skirt", "bottom", "Kashmiri Royal", ["Burgundy Tartan"], 3, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Silver Tilla Woven Velvet Tailored Winter Blazer", "jacket", "outerwear", "Kashmiri Royal", ["Wine Velvet"], 4, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Hand-Spun Pure Pashmina Open Front Longline Shrug", "shrug", "outerwear", "Kashmiri Royal", ["Oatmeal Heather"], 3, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Patan Double-Ikat Pure Silk Royal Festive Gown Dress", "dress", "onepiece", "Gujarati Royal", ["Sindoor Red"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Rann Sunset Coral-Embroidered Evening Maxi Dress", "dress", "onepiece", "Gujarati Royal", ["Coral Sunset"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Gir Forest Organic Khadi Cotton Tiered Day Dress", "dress", "onepiece", "Gujarati Royal", ["Leaf Green"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Kutchi Rabari Mirror-Work Handcrafted Kediya Top", "top", "top", "Gujarati Royal", ["Turmeric Yellow"], 2, ["casual", "college", "office"]),
            ("item_5.jfif", "Surat Diamond Jacquard Tailored Silk Peplum Blouse", "top", "top", "Gujarati Royal", ["Royal Blue"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Sabarmati Breathable Cotton Active Stretch Kurti Top", "top", "top", "Gujarati Royal", ["Off-White Khadi"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Ahmedabad Heritage Handloom Tailored Straight Pants", "pants", "bottom", "Gujarati Royal", ["Desert Khaki"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Bandhej Fine Tie-Dye Silk Flared Chaniya Skirt", "skirt", "bottom", "Gujarati Royal", ["Parrot Green"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Kutch Artisan Mirror-Encrusted Festive Crop Jacket", "jacket", "outerwear", "Gujarati Royal", ["Midnight Black Mirror"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Ajrakh Natural Indigo Block-Print Reversible Open Shrug", "shrug", "outerwear", "Gujarati Royal", ["Ajrakh Indigo"], 2, ["casual", "travel", "party", "date"]),
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
            ("item_1.jfif", "Kanchipuram Heavy Gold Zari Temple Border Silk Gown Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Kalyana Red"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Mylapore Peacock Blue Raw Silk Evening Dress", "dress", "onepiece", "Tamil Temple Heritage", ["Peacock Blue"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Marina Beach Breathable Handloom Cotton Sundress", "dress", "onepiece", "Tamil Temple Heritage", ["Coral Orange"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Chettinad Geometric Woven Checks Cotton Kurti Top", "top", "top", "Tamil Temple Heritage", ["Mustard Yellow"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Salem Pure Silk Tailored High-Neck Formal Blouse", "top", "top", "Tamil Temple Heritage", ["Forest Green"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Coimbatore Handloom Breathable Active Movement Top", "top", "top", "Tamil Temple Heritage", ["Natural Cream"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Madras Checks Handwoven Cotton Tailored Trousers", "pants", "bottom", "Tamil Temple Heritage", ["Indigo Checks"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Madurai Sungudi Tie-Dye Pleated Festive Midi Skirt", "skirt", "bottom", "Tamil Temple Heritage", ["Maroon Gold"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Thanjavur Antique Gold Embroidered Silk Koti Blazer", "jacket", "outerwear", "Tamil Temple Heritage", ["Temple Gold"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Gold Tissue Temple Border Artisan Open Shrug", "shrug", "outerwear", "Tamil Temple Heritage", ["Gold Tissue"], 1, ["casual", "travel", "party", "date"]),
        ]
    },
    # 8. MAHARASHTRA
    {
        "id": 8,
        "name": "Aarohi Deshmukh",
        "username": "aarohi_deshmukh",
        "role": "Film Producer & Handloom Revivalist (Mumbai & Pune)",
        "style_persona": "Paithani Silk, Nauvari & Lavani Festive Grandeur",
        "preferred_colors": ["Peacock Teal", "Nashik Grape", "Haldi Yellow", "Chhatrapati Saffron", "Charcoal Slate"],
        "temp_pref": "Moderate / Coastal",
        "bio": "Opulent Paithani silk motifs, peacock zari borders, Puneri handloom kurtas, Lavani pleats, and modern Bollywood red-carpet elegance.",
        "badge": "MAHARASHTRA · PAITHANI",
        "color": (255, 140, 0),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Royal Paithani Peacock Border Pure Silk Gown Dress", "dress", "onepiece", "Maharashtrian Royal", ["Peacock Teal"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Shaniwar Wada Midnight Purple Silk Evening Dress", "dress", "onepiece", "Maharashtrian Royal", ["Nashik Grape"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Konkan Coast Breezy Organic Cotton Sundress", "dress", "onepiece", "Maharashtrian Royal", ["Haldi Yellow"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Puneri Cotton Handloom Kashti Blouse Kurti Top", "top", "top", "Maharashtrian Royal", ["Saffron Orange"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Bombay Heritage Tailored Mulberry Silk Formal Top", "top", "top", "Maharashtrian Royal", ["Charcoal Slate"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Sahyadri Trekking Stretch Cotton Active Tunic Top", "top", "top", "Maharashtrian Royal", ["Earthy Brown"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Kolhapuri Handwoven Cotton Straight Tailored Pants", "pants", "bottom", "Maharashtrian Royal", ["Off-White"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Paithani Zari Border Flared Pleated Ethnic Skirt", "skirt", "bottom", "Maharashtrian Royal", ["Emerald Gold"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Maharashtrian Brocade Tailored Festive Koti Jacket", "jacket", "outerwear", "Maharashtrian Royal", ["Ruby Brocade"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Solapur Handspun Cotton Lightweight Layering Shrug", "shrug", "outerwear", "Maharashtrian Royal", ["Indigo Dye"], 1, ["casual", "travel", "party", "date"]),
        ]
    },
    # 9. ASSAM
    {
        "id": 9,
        "name": "Mayuri Barua",
        "username": "mayuri_barua",
        "role": "Silk Sericulturist & Traditional Artisan (Guwahati & Sualkuchi)",
        "style_persona": "Golden Muga Silk & Bihu Festival Handloom Grace",
        "preferred_colors": ["Golden Muga", "Sindoor Red", "Brahmaputra Sky", "Eri Cream", "Kaziranga Forest"],
        "temp_pref": "Moderate / Lush",
        "bio": "Lustrous indigenous Golden Muga silk, red Kingkhap motifs, handspun Eri peace-silk tunics, Bihu dancer silhouettes, and misty river valley elegance.",
        "badge": "ASSAM · MUGA SILK",
        "color": (218, 165, 32),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Ancestral Golden Muga Silk Red Kapa Saree Dress", "dress", "onepiece", "Assam Silk Heritage", ["Golden Muga"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Brahmaputra Sunset Peacock Blue Silk Evening Gown", "dress", "onepiece", "Assam Silk Heritage", ["Brahmaputra Sky"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Majuli Island Handwoven Organic Cotton Day Dress", "dress", "onepiece", "Assam Silk Heritage", ["Eri Cream"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Bihu Red-Bordered Eri Silk Handwoven Kurti Top", "top", "top", "Assam Silk Heritage", ["Sindoor Red"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Guwahati Botanical Dyed Silk Formal Peplum Blouse", "top", "top", "Assam Silk Heritage", ["Kaziranga Forest"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Tea Garden Breathable Cotton Active Movement Top", "top", "top", "Assam Silk Heritage", ["Leaf Green"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Assamese Handloom Raw Cotton Straight Slacks", "pants", "bottom", "Assam Silk Heritage", ["Natural Off-White"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Muga Weave Diamond Jaapi Motif Flared Skirt", "skirt", "bottom", "Assam Silk Heritage", ["Champagne Gold"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Eri Silk Handwoven Tailored Structure Vest Jacket", "jacket", "outerwear", "Assam Silk Heritage", ["Earth Beige"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Golden Muga Floral Border Open Front Shrug", "shrug", "outerwear", "Assam Silk Heritage", ["Golden Honey"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 10. GOA
    {
        "id": 10,
        "name": "Kiara Fernandes",
        "username": "kiara_fernandes",
        "role": "Resort Architect & Boutique Hotelier (Panaji & Candolim)",
        "style_persona": "Indo-Portuguese Coastal Resort & Bohemian Fado Linen",
        "preferred_colors": ["Portuguese Azulejo Blue", "Terracotta Ochre", "Sunset Coral", "Cashew Cream", "Seafoam Green"],
        "temp_pref": "Warm / Coastal",
        "bio": "Breezy linen jumpsuits, tiered resort sundresses, Portuguese azulejo floral prints, hand-crochet lace shrugs, and sun-drenched coastal ease.",
        "badge": "GOA · COASTAL LINEN",
        "color": (64, 224, 208),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Fontainhas Bohemian Silk Resort Evening Maxi Dress", "dress", "onepiece", "Goan Resort", ["Sunset Coral"], 1, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Panjim Sunset Gold Chiffon Cocktail Dress", "dress", "onepiece", "Goan Resort", ["Azulejo Blue"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Anjuna Beachside Breezy Organic Linen Sundress", "dress", "onepiece", "Goan Resort", ["Cashew Cream"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Portuguese Azulejo Tile-Print Cotton Blouse Top", "top", "top", "Goan Resort", ["Cobalt White"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Old Goa Tailored Linen Collared Formal Shirt", "top", "top", "Goan Resort", ["Terracotta"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Goan Coastal Surfer Stretch Breathable Active Top", "top", "top", "Goan Resort", ["Seafoam Green"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Mandovi River White Linen Wide-Leg Tailored Trousers", "pants", "bottom", "Goan Resort", ["Crisp White"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Calangute Floral Print Tiered Cotton Midi Skirt", "skirt", "bottom", "Goan Resort", ["Sunset Tropical"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Heritage Colonial Tailored Raw Linen Summer Blazer", "jacket", "outerwear", "Goan Resort", ["Sand Khaki"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Crochet Lace Hand-Knit Coastal Breezy Shrug", "shrug", "outerwear", "Goan Resort", ["Shell Cream"], 1, ["casual", "travel", "party", "date"]),
        ]
    },
    # 11. UTTAR PRADESH / LUCKNOW
    {
        "id": 11,
        "name": "Ayesha Siddiqui",
        "username": "ayesha_siddiqui",
        "role": "Calligrapher & Heritage Couturier (Lucknow & Varanasi)",
        "style_persona": "Lucknowi Chikankari & Nawabi Awadh Grace",
        "preferred_colors": ["Pristine Ivory", "Gulabi Rose", "Pista Mint", "Nawabi Lavender", "Chandi Silver"],
        "temp_pref": "Moderate / Refined",
        "bio": "Ethereal white-on-white shadow-work Chikankari, pure organza kurtas, fine Mukaish metallic highlights, flowing ghararas, and timeless Awadhi poise.",
        "badge": "LUCKNOW · CHIKANKARI",
        "color": (219, 112, 147),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Awadhi Nazakat Hand-Embroidered Chikankari Silk Anarkali Dress", "dress", "onepiece", "Lucknowi Royal", ["Pristine Ivory"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Hazratganj Twilight Emerald Chanderi Evening Dress", "dress", "onepiece", "Lucknowi Royal", ["Emerald Teal"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Lucknowi Bakhiya Stitch Pastel Cotton Day Dress", "dress", "onepiece", "Lucknowi Royal", ["Gulabi Rose"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Pure Georgette Fine Chikankari Short Kurti Top", "top", "top", "Lucknowi Royal", ["Pista Mint"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Nawabi Court Tailored Angrakha Formal Silk Blouse", "top", "top", "Lucknowi Royal", ["Nawabi Lavender"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Breathable Cotton Chikankari Active Movement Top", "top", "top", "Lucknowi Royal", ["Chandi Silver"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Lakhnavi Brocade Border Silk Sharara Trousers", "pants", "bottom", "Lucknowi Royal", ["Pale Lavender"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Mukaish Work Hand-Embellished Flared Georgette Skirt", "skirt", "bottom", "Lucknowi Royal", ["Silver Ivory"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Brocade Quilted Heritage Tailored Awadh Koti Jacket", "jacket", "outerwear", "Lucknowi Royal", ["Pale Gold"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Chiffon Shadow-Work Open Flowing Shrug", "shrug", "outerwear", "Lucknowi Royal", ["Blush White"], 1, ["casual", "travel", "party", "date"]),
        ]
    },
    # 12. TELANGANA & ANDHRA
    {
        "id": 12,
        "name": "Sahithi Reddy",
        "username": "sahithi_reddy",
        "role": "Fintech Founder & Handloom Connoisseur (Hyderabad)",
        "style_persona": "Pochampally Ikkat, Gadwal Zari & Golconda Chic",
        "preferred_colors": ["Pochampally Magenta", "Gadwal Mustard", "Charminar Bronze", "Kalamkari Ochre", "Nizam Pearl"],
        "temp_pref": "Warm / Modern",
        "bio": "Geometric Pochampally tie-dye ikkat dresses, heavy Gadwal silk borders, Kalamkari block motifs, and high-tech corporate executive style.",
        "badge": "HYDERABAD · IKKAT",
        "color": (199, 21, 133),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Pochampally Double-Ikkat Geometric Silk Gown Dress", "dress", "onepiece", "Telangana Handloom", ["Pochampally Magenta"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Golconda Twilight Crimson Brocade Evening Dress", "dress", "onepiece", "Telangana Handloom", ["Charminar Bronze"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Warangal Handloom Pure Cotton Breathable Day Dress", "dress", "onepiece", "Telangana Handloom", ["Kalamkari Ochre"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Gadwal Zari Border Handwoven Silk Kurti Top", "top", "top", "Telangana Handloom", ["Gadwal Mustard"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Hyderabad Tech-City Crisp Silk-Cotton Formal Shirt", "top", "top", "Telangana Handloom", ["Nizam Pearl"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Telangana Handloom Stretch Active Movement Top", "top", "top", "Telangana Handloom", ["Graphite Black"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Narayanpet Woven Border Straight Cut Slacks", "pants", "bottom", "Telangana Handloom", ["Dark Slate"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Ikkat Diamond Patterned Flared Ethnic Skirt", "skirt", "bottom", "Telangana Handloom", ["Ruby Red Ikkat"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Deccan Heritage Gold Jacquard Tailored Koti Blazer", "jacket", "outerwear", "Telangana Handloom", ["Antique Gold"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Hand-Dyed Pochampally Weave Casual Open Shrug", "shrug", "outerwear", "Telangana Handloom", ["Navy Ikkat"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 13. HIMACHAL PRADESH
    {
        "id": 13,
        "name": "Tanya Sharma",
        "username": "tanya_sharma",
        "role": "Botanist & Alpine Resort Owner (Manali & Shimla)",
        "style_persona": "Kullu Geometric Woolens & Himalayan Alpine Warmth",
        "preferred_colors": ["Kullu Crimson", "Pine Forest Green", "Chamba Blue", "Alpine Snow", "Apple Orchard Amber"],
        "temp_pref": "Cold / Mountain",
        "bio": "Handwoven Kullu caps and geometric woolen borders, fine Himachali pashmina shawls, apple orchard corduroys, and crisp mountain comfort.",
        "badge": "HIMACHAL · KULLU",
        "color": (46, 139, 87),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Kullu Geometric Bordered Pashmina Woolen Maxi Dress", "dress", "onepiece", "Himachal Alpine", ["Kullu Crimson"], 3, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Shimla Twilight Pine-Green Cashmere Evening Dress", "dress", "onepiece", "Himachal Alpine", ["Pine Forest Green"], 3, ["party", "date", "formal"]),
            ("item_3.jfif", "Manali Alpine Wildflower Print Chiffon Day Dress", "dress", "onepiece", "Himachal Alpine", ["Chamba Blue"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Hand-Spun Kinnauri Embroidered Woolen Kurti Top", "top", "top", "Himachal Alpine", ["Apple Orchard Amber"], 2, ["casual", "college", "office"]),
            ("item_5.jfif", "Himachal Apple Orchard Tailored Fine Wool Blouse", "top", "top", "Himachal Alpine", ["Alpine Snow"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Himalayan Trail Active Stretch Merino Thermal Top", "top", "top", "Himachal Alpine", ["Mountain Grey"], 3, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Kullu Wool Blend Tailored Warm Pleated Trousers", "pants", "bottom", "Himachal Alpine", ["Charcoal Wool"], 3, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Spiti Valley Geometric Border Flared Woolen Skirt", "skirt", "bottom", "Himachal Alpine", ["Burgundy Tartan"], 3, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Handwoven Kullu Pattern Structured Tweed Jacket", "jacket", "outerwear", "Himachal Alpine", ["Forest Tweed"], 4, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Alpine Pure Wool Cable-Knit Open Front Shrug", "shrug", "outerwear", "Himachal Alpine", ["Cream Wool"], 3, ["casual", "travel", "party", "date"]),
        ]
    },
    # 14. ODISHA
    {
        "id": 14,
        "name": "Shreya Mohapatra",
        "username": "shreya_mohapatra",
        "role": "Odissi Exponent & Temple Historian (Bhubaneswar & Puri)",
        "style_persona": "Sambalpuri Ikat & Konark Temple Silk Heritage",
        "preferred_colors": ["Sambalpuri Crimson", "Konark Black", "Ganga-Jamuna Ochre", "Puri Shell White", "Temple Terracotta"],
        "temp_pref": "Moderate / Coastal",
        "bio": "Hand-tied Sambalpuri bandha ikat, Pasapalli checkerboard silks, Konark wheel motifs, Kotpad natural dye vegetable cottons, and classical grace.",
        "badge": "ODISHA · SAMBALPURI",
        "color": (165, 42, 42),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Sambalpuri Handloom Silk Pasapalli Checkerboard Gown Dress", "dress", "onepiece", "Odisha Heritage", ["Sambalpuri Crimson"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Konark Wheel Motif Midnight Blue Silk Evening Dress", "dress", "onepiece", "Odisha Heritage", ["Konark Black"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Chilika Lake Organic Breathable Handloom Day Dress", "dress", "onepiece", "Odisha Heritage", ["Puri Shell White"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Bomkai Weave Fish Motif Pure Cotton Kurti Top", "top", "top", "Odisha Heritage", ["Ganga-Jamuna Ochre"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Bhubaneswar Heritage Tailored Mulberry Silk Blouse", "top", "top", "Odisha Heritage", ["Temple Terracotta"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Coastal Handloom Cotton Stretch Movement Active Top", "top", "top", "Odisha Heritage", ["Indigo Cotton"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Kotpad Plant-Dyed Cotton Straight Tailored Trousers", "pants", "bottom", "Odisha Heritage", ["Madder Brown"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Sambalpuri Floral Ikat Pleated Flared Midi Skirt", "skirt", "bottom", "Odisha Heritage", ["Crimson Ikat"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Odisha Heritage Handloom Structured Crop Blazer", "jacket", "outerwear", "Odisha Heritage", ["Black Ikat"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Natural Tussar Silk Open Drape Artisanal Shrug", "shrug", "outerwear", "Odisha Heritage", ["Raw Tussar"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 15. UNITED KINGDOM (LONDON)
    {
        "id": 15,
        "name": "Emma Watson",
        "username": "emma_watson",
        "role": "Oxford Academic & Literary Stylist (London)",
        "style_persona": "Savile Row Tailoring & British Heritage Trench",
        "preferred_colors": ["Savile Navy", "Camel Hair", "Oxford Blue", "Tartan Hunter", "English Ivory"],
        "temp_pref": "Cool / Maritime",
        "bio": "Sharp bespoke tailoring, classic gabardine double-breasted trench coats, pleated wool midi skirts, crisp poplin shirts, and quintessential British intellect.",
        "badge": "UK · SAVILE ROW",
        "color": (25, 25, 112),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Mayfair High-Society Tailored Silk Evening Gown Dress", "dress", "onepiece", "British Heritage", ["Savile Navy"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Kensington Velvet Cocktail Little Black Dress", "dress", "onepiece", "British Heritage", ["Velvet Noir"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Cotswolds English Rose Meadow Floral Tea Dress", "dress", "onepiece", "British Heritage", ["English Ivory"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Oxford Blue Crisp Oxford Cotton Collared Shirt Top", "top", "top", "British Heritage", ["Oxford Blue"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Savile Row Pinstripe Tailored Silk-Cotton Blouse", "top", "top", "British Heritage", ["Pinstripe Navy"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Hyde Park Morning Jogger Technical Stretch Active Top", "top", "top", "British Heritage", ["Heather Grey"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Savile Row High-Waisted Wool Tailored Trousers", "pants", "bottom", "British Heritage", ["Camel Tan"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Scottish Tartan Plaid Pleated A-Line Midi Skirt", "skirt", "bottom", "British Heritage", ["Tartan Hunter"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "British Heritage Double-Breasted Camel Trench Coat", "jacket", "outerwear", "British Heritage", ["Classic Camel"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Fine Merino Wool Ribbed Open Layering Cardigan Shrug", "shrug", "outerwear", "British Heritage", ["Charcoal Knit"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 16. FRANCE (PARIS)
    {
        "id": 16,
        "name": "Camille Laurent",
        "username": "camille_laurent",
        "role": "Fashion Editor & Atelier Director (Paris)",
        "style_persona": "Parisian Haute Couture, Saint-Germain Linen & Tweed",
        "preferred_colors": ["Noir Absolu", "Parisian Ecru", "Burgundy Rouge", "French Navy", "Blush Silk"],
        "temp_pref": "Moderate / Chic",
        "bio": "Effortless Saint-Germain-des-Prés tailoring, Chanel-inspired boucle tweed jackets, fluid silk slip dresses, cigarette trousers, and nonchalant Gallic chic.",
        "badge": "FRANCE · HAUTE COUTURE",
        "color": (47, 79, 79),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Haute Couture Silk Chiffon Evening Drape Gown Dress", "dress", "onepiece", "Parisian Chic", ["Burgundy Rouge"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Le Marais Asymmetrical Black Crepe Cocktail Dress", "dress", "onepiece", "Parisian Chic", ["Noir Absolu"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Saint-Tropez French Riviera Striped Linen Day Dress", "dress", "onepiece", "Parisian Chic", ["Parisian Ecru"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Saint-Germain Silk Georgette Lavalliere Bow Blouse", "top", "top", "Parisian Chic", ["Blush Silk"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Rue Saint-Honore Tailored Crisp White Poplin Shirt", "top", "top", "Parisian Chic", ["French Navy"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Parisian Barre & Pilates Breathable Active Stretch Top", "top", "top", "Parisian Chic", ["Slate Noir"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Montmartre Cigarette Ankle-Crop Tailored Trousers", "pants", "bottom", "Parisian Chic", ["Classic Noir"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Champs-Elysees Pleated French Wool Flared Skirt", "skirt", "bottom", "Parisian Chic", ["Houndstooth Grey"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Chanel-Style Boucle Tweed Tailored Cropped Jacket", "jacket", "outerwear", "Parisian Chic", ["Tweed Ecru"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "French Alpaca Knit Minimalist Open Shrug", "shrug", "outerwear", "Parisian Chic", ["Cream Alpaca"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 17. JAPAN (TOKYO)
    {
        "id": 17,
        "name": "Hana Tanaka",
        "username": "hana_tanaka",
        "role": "Architectural Designer & Ceramicist (Tokyo & Kyoto)",
        "style_persona": "Tokyo Avant-Garde Minimalist, Kimono Fusion & Raw Denim",
        "preferred_colors": ["Ink Sumi Black", "Wabi-Sabi Cream", "Indigo Denim", "Bamboo Sage", "Cherry Blossom Blush"],
        "temp_pref": "Moderate / Zen",
        "bio": "Deconstructed origami drapery, raw Okayama selvedge denim, modern haori kimono-sleeve coats, asymmetric tunic silhouettes, and zen sculptural lines.",
        "badge": "JAPAN · AVANT-GARDE",
        "color": (75, 0, 130),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Kyoto Nishijin-Ori Gold Silk Kimono Fusion Dress", "dress", "onepiece", "Tokyo Minimalist", ["Ink Sumi Black"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Roppongi Twilight Minimalist Jet-Black Asymmetric Dress", "dress", "onepiece", "Tokyo Minimalist", ["Pure Noir"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Kamakura Natural Linen Origami Drape Day Dress", "dress", "onepiece", "Tokyo Minimalist", ["Wabi-Sabi Cream"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Ginza Crisp Cotton Minimalist Asymmetrical Tunic Top", "top", "top", "Tokyo Minimalist", ["Bamboo Sage"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Tokyo Architectural Tailored Stand-Collar Silk Shirt", "top", "top", "Tokyo Minimalist", ["Raw Indigo"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Zen Movement Breathable Bamboo Active Stretch Top", "top", "top", "Tokyo Minimalist", ["Cherry Blossom"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Okayama Selvedge Denim Wide-Leg Pleated Trousers", "pants", "bottom", "Tokyo Minimalist", ["Dark Selvedge"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Harajuku Origami Fold Pleated Structural Midi Skirt", "skirt", "bottom", "Tokyo Minimalist", ["Charcoal Wool"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Modern Haori Kimono Sleeve Tailored Woolen Jacket", "jacket", "outerwear", "Tokyo Minimalist", ["Midnight Indigo"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Wabi-Sabi Deconstructed Open Front Knit Shrug", "shrug", "outerwear", "Tokyo Minimalist", ["Sand Taupe"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 18. SOUTH KOREA (SEOUL)
    {
        "id": 18,
        "name": "Ji-woo Park",
        "username": "jiwoo_park",
        "role": "Music Video Art Director & K-Style Influencer (Seoul)",
        "style_persona": "Seoul K-Fashion Oversized Streetwear & Modern Hanbok",
        "preferred_colors": ["Seoul Neon Lime", "Hanbok Pastel Pink", "K-Pop Jet Black", "Lilac Mist", "Oversized Oatmeal"],
        "temp_pref": "Moderate / Trend",
        "bio": "Oversized structured blazers, modern organza hanbok skirts, cropped technical jackets, pleated tennis skirts, and hyper-clean Dongdaemun trendsetting.",
        "badge": "KOREA · K-FASHION",
        "color": (255, 20, 147),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Modern Hanbok Silk Organza Pastel Evening Gown Dress", "dress", "onepiece", "Seoul K-Style", ["Hanbok Pastel Pink"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Gangnam Glamour Cut-Out Midnight Velvet Cocktail Dress", "dress", "onepiece", "Seoul K-Style", ["K-Pop Jet Black"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Jeju Island Floral Chiffon Tiered Day Dress", "dress", "onepiece", "Seoul K-Style", ["Lilac Mist"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Hongdae Oversized Graphic Drop-Shoulder Cotton Top", "top", "top", "Seoul K-Style", ["Seoul Neon Lime"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Teheran-ro Minimalist Tailored Satin Office Blouse", "top", "top", "Seoul K-Style", ["Oversized Oatmeal"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "K-Pop Studio High-Stretch Technical Active Crop Top", "top", "top", "Seoul K-Style", ["Matte Black"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Seongsu-dong High-Waisted Straight-Leg Chino Trousers", "pants", "bottom", "Seoul K-Style", ["Khaki Camel"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Modern Jeogori Pleated Tiered Tennis Midi Skirt", "skirt", "bottom", "Seoul K-Style", ["Pastel Ivory"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Seoul Fashion Week Oversized Boxy Tailored Blazer", "jacket", "outerwear", "Seoul K-Style", ["Pinstripe Charcoal"], 3, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Soft Cropped Fluffy Knit Open Front Cardigan Shrug", "shrug", "outerwear", "Seoul K-Style", ["Baby Lilac"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 19. USA (NEW YORK CITY)
    {
        "id": 19,
        "name": "Rachel Adams",
        "username": "rachel_adams",
        "role": "Tech VC & Manhattan Contemporary Art Trustee (New York)",
        "style_persona": "Manhattan High-Street Minimalist & SoHo Downtown Chic",
        "preferred_colors": ["Matte Black", "Asphalt Grey", "Camel Tan", "Bleached Denim", "Chelsea White"],
        "temp_pref": "Four-Season / Urban",
        "bio": "All-black Manhattan power uniforms, leather moto jackets, distressed relaxed denim, cashmere crewnecks, and sleek Chelsea-gallery effortless edge.",
        "badge": "NYC · SOHO CHIC",
        "color": (105, 105, 105),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Tribeca Black-Tie Bias-Cut Silk Slip Gown Dress", "dress", "onepiece", "Manhattan Minimalist", ["Matte Black"], 2, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Meatpacking District Satin Cut-Out Cocktail Dress", "dress", "onepiece", "Manhattan Minimalist", ["Asphalt Grey"], 2, ["party", "date", "formal"]),
            ("item_3.jfif", "Hamptons Summer Striped Poplin Button-Front Day Dress", "dress", "onepiece", "Manhattan Minimalist", ["Chelsea White"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "SoHo Relaxed Denim Button-Down Boyfriend Shirt Top", "top", "top", "Manhattan Minimalist", ["Bleached Denim"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Wall Street Structured Pima Cotton Poplin Tailored Top", "top", "top", "Manhattan Minimalist", ["Camel Tan"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Equinox High-Performance Seamless Active Compression Top", "top", "top", "Manhattan Minimalist", ["Jet Black"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Madison Avenue Tailored Pleated Wide-Leg Pants", "pants", "bottom", "Manhattan Minimalist", ["Dark Charcoal"], 2, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Brooklyn Leather Look High-Waist A-Line Midi Skirt", "skirt", "bottom", "Manhattan Minimalist", ["Cognac Brown"], 2, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Downtown Moto Genuine Leather Asymmetric Biker Jacket", "jacket", "outerwear", "Manhattan Minimalist", ["Noir Leather"], 4, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Manhattan Cashmere Blend Drape Front Open Shrug", "shrug", "outerwear", "Manhattan Minimalist", ["Heather Grey"], 2, ["casual", "travel", "party", "date"]),
        ]
    },
    # 20. ITALY (MILAN / MONACO RIVIERA)
    {
        "id": 20,
        "name": "Evelyn Robinson",
        "username": "evelyn_robinson",
        "role": "Yachting & Luxury Consultant (Monaco & Milan)",
        "style_persona": "Riviera Quiet Luxury & Resort Haute Glamour",
        "preferred_colors": ["Riviera Mediterranean Blue", "Yacht White", "Champagne Gold", "Linen Sand", "Coral Sunset"],
        "temp_pref": "Warm / Mediterranean",
        "bio": "Monte Carlo grand casino evening silks, Port Hercules yachting crisp linens, Cap d'Antibes breezy sundresses, and Cannes festival tailoring.",
        "badge": "MONACO · RIVIERA LUXE",
        "color": (70, 130, 180),
        "is_punjab": False,
        "is_kerala": False,
        "items": [
            ("item_1.jfif", "Monte Carlo Grand Casino Silk Slip Gown", "dress", "onepiece", "Riviera Luxe", ["Champagne Gold"], 1, ["wedding", "formal", "party"]),
            ("item_2.jfif", "Port Hercules Yachting Crisp White Linen Dress", "dress", "onepiece", "Riviera Luxe", ["Yacht White"], 1, ["party", "date", "formal"]),
            ("item_3.jfif", "Larvotto Beachfront Silk Halter Day Dress", "dress", "onepiece", "Riviera Luxe", ["Mediterranean Blue"], 1, ["casual", "travel", "college"]),
            ("item_4.jfif", "Cap d'Antibes Breathable Raw Linen Tunic Top", "top", "top", "Riviera Luxe", ["Linen Sand"], 1, ["casual", "college", "office"]),
            ("item_5.jfif", "Menton Citrus Tailored Pure Silk Executive Blouse", "top", "top", "Riviera Luxe", ["Lemon Sorbet"], 2, ["office", "formal", "date"]),
            ("item_6.jfif", "Italian Riviera Breathable Modal Active Movement Top", "top", "top", "Riviera Luxe", ["Sea Breeze"], 1, ["workout", "travel", "casual"]),
            ("item_7.jfif", "Saint-Tropez High-Waist Flowing Palazzo Pants", "pants", "bottom", "Riviera Luxe", ["Sand Beige"], 1, ["office", "formal", "wedding"]),
            ("item_8.jfif", "Hotel de Paris Pleated Silk Resort Skirt", "skirt", "bottom", "Riviera Luxe", ["Coral Sunset"], 1, ["college", "casual", "date", "party", "workout"]),
            ("item_9.jfif", "Cannes Red Carpet Double-Breasted Silk Blazer", "jacket", "outerwear", "Riviera Luxe", ["Ivory White"], 2, ["wedding", "formal", "office"]),
            ("item_10.jfif", "Riviera Coastal Evening Cashmere Open Shrug", "shrug", "outerwear", "Riviera Luxe", ["Champagne Cream"], 2, ["casual", "travel", "party", "date"]),
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
    # Also delete any planned_outfits / history that may reference old items
    cursor.execute("DELETE FROM planned_outfits")
    cursor.execute("DELETE FROM outfit_history")
    conn.commit()

    total_items = 0

    for u_idx, u in enumerate(REGIONAL_USERS_10):
        uid = u["id"]
        user_dir = USER_WARDROBES_DIR / str(uid)
        user_dir.mkdir(exist_ok=True)

        # Clear existing old images from user_dir
        for old_f in user_dir.glob("*.jfif"):
            try:
                old_f.unlink()
            except Exception:
                pass

        colors_json = json.dumps(u["preferred_colors"])

        cursor.execute("SELECT id FROM users WHERE id = ?", (uid,))
        exists = cursor.fetchone()
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

        cat_counts = {}

        for i_idx, item in enumerate(u["items"]):
            fname, iname, cat, grp, st, colors, warmth, item_occs = item

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
                json.dumps(item_occs)
            ))
            total_items += 1

    conn.commit()
    conn.close()
    print(f"\nSUCCESS! Seeded 20 distinct wardrobes with exactly 10 new items each ({total_items} items total).")

if __name__ == "__main__":
    migrate_database()
