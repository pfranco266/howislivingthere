"""
Step 4: Merge geocoded posts into one location per city+country.
Outputs the final locations.json consumed by the React frontend.

Input:  data/raw/geocoded.json
Output: src/data/locations.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# -- Paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "scraper" / "data" / "raw" / "geocoded.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "data" / "locations.json"

# -- Region mapping ----------------------------------------------------
COUNTRY_TO_REGION = {
    # Europe
    "Portugal": "Europe", "Spain": "Europe", "France": "Europe",
    "Germany": "Europe", "Netherlands": "Europe", "Belgium": "Europe",
    "Switzerland": "Europe", "Austria": "Europe", "Italy": "Europe",
    "Greece": "Europe", "Croatia": "Europe", "Slovenia": "Europe",
    "Czech Republic": "Europe", "Czechia": "Europe", "Slovakia": "Europe",
    "Hungary": "Europe", "Poland": "Europe", "Romania": "Europe",
    "Bulgaria": "Europe", "Serbia": "Europe", "Montenegro": "Europe",
    "Albania": "Europe", "North Macedonia": "Europe", "Bosnia and Herzegovina": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe",
    "Finland": "Europe", "Iceland": "Europe", "Ireland": "Europe",
    "United Kingdom": "Europe", "UK": "Europe",
    "Estonia": "Europe", "Latvia": "Europe", "Lithuania": "Europe",
    "Georgia": "Europe", "Armenia": "Europe", "Azerbaijan": "Europe",
    "Ukraine": "Europe", "Moldova": "Europe", "Belarus": "Europe",
    "Russia": "Europe", "Turkey": "Europe", "Cyprus": "Europe",
    "Malta": "Europe", "Luxembourg": "Europe",

    # Americas
    "United States": "Americas", "USA": "Americas", "Canada": "Americas",
    "Mexico": "Americas", "Brazil": "Americas", "Argentina": "Americas",
    "Chile": "Americas", "Colombia": "Americas", "Peru": "Americas",
    "Ecuador": "Americas", "Bolivia": "Americas", "Paraguay": "Americas",
    "Uruguay": "Americas", "Venezuela": "Americas", "Guyana": "Americas",
    "Suriname": "Americas", "Cuba": "Americas", "Dominican Republic": "Americas",
    "Puerto Rico": "Americas", "Jamaica": "Americas", "Haiti": "Americas",
    "Costa Rica": "Americas", "Panama": "Americas", "Guatemala": "Americas",
    "Honduras": "Americas", "El Salvador": "Americas", "Nicaragua": "Americas",
    "Belize": "Americas",

    # Asia
    "Japan": "Asia", "South Korea": "Asia", "China": "Asia", "Taiwan": "Asia",
    "Hong Kong": "Asia", "Singapore": "Asia", "Thailand": "Asia",
    "Vietnam": "Asia", "Cambodia": "Asia", "Laos": "Asia", "Myanmar": "Asia",
    "Malaysia": "Asia", "Indonesia": "Asia", "Philippines": "Asia",
    "India": "Asia", "Sri Lanka": "Asia", "Nepal": "Asia", "Bangladesh": "Asia",
    "Pakistan": "Asia", "Afghanistan": "Asia", "Iran": "Asia", "Iraq": "Asia",
    "Saudi Arabia": "Asia", "UAE": "Asia", "United Arab Emirates": "Asia",
    "Qatar": "Asia", "Kuwait": "Asia", "Bahrain": "Asia", "Oman": "Asia",
    "Yemen": "Asia", "Jordan": "Asia", "Lebanon": "Asia", "Israel": "Asia",
    "Palestine": "Asia", "Syria": "Asia", "Kazakhstan": "Asia",
    "Uzbekistan": "Asia", "Kyrgyzstan": "Asia", "Tajikistan": "Asia",
    "Turkmenistan": "Asia", "Mongolia": "Asia",

    # Africa
    "South Africa": "Africa", "Kenya": "Africa", "Nigeria": "Africa",
    "Ghana": "Africa", "Ethiopia": "Africa", "Tanzania": "Africa",
    "Uganda": "Africa", "Rwanda": "Africa", "Senegal": "Africa",
    "Ivory Coast": "Africa", "Côte d'Ivoire": "Africa", "Cameroon": "Africa",
    "Morocco": "Africa", "Tunisia": "Africa", "Algeria": "Africa",
    "Egypt": "Africa", "Libya": "Africa", "Sudan": "Africa",
    "Mozambique": "Africa", "Zimbabwe": "Africa", "Zambia": "Africa",
    "Botswana": "Africa", "Namibia": "Africa", "Madagascar": "Africa",

    # Oceania
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "Papua New Guinea": "Oceania",
}

DEFAULT_REGION = "Other"

MAX_COMMENTS_PER_POST = 20


def slugify(text):
    """Turn 'São Paulo, Brazil' into 'sao-paulo-brazil'."""
    text = text.lower().strip()
    # Normalize common accented chars
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ò": "o", "õ": "o", "ô": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ñ": "n", "ç": "c", "ß": "ss",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text


def normalize_key(city, country):
    """Canonical grouping key for merging."""
    return f"{(city or '').strip().lower()}|{(country or '').strip().lower()}"


def get_region(country):
    return COUNTRY_TO_REGION.get(country, DEFAULT_REGION)


def build_location(city, country, precision, lat, lng, posts_data):
    """Build one location object from a group of posts."""
    city_slug = slugify(city) if city else "unknown"
    country_slug = slugify(country) if country else "unknown"
    loc_id = f"{city_slug}-{country_slug}"

    # Sort posts by upvotes descending
    posts_data.sort(key=lambda p: p["score"], reverse=True)

    posts_out = []
    for post in posts_data:
        # Sort comments by score descending, keep top 5
        comments_sorted = sorted(post.get("comments", []), key=lambda c: c["score"], reverse=True)
        comments_out = [
            {
                "text": c["body"],
                "score": c["score"],
                "author": c["author"],
                "redditId": c["id"],
            }
            for c in comments_sorted[:MAX_COMMENTS_PER_POST]
        ]

        posts_out.append({
            "redditId": post["id"],
            "title": post["title"],
            "upvotes": post["score"],
            "url": post.get("permalink", f"https://www.reddit.com/r/howislivingthere/comments/{post['id']}"),
            "comments": comments_out,
        })

    return {
        "id": loc_id,
        "city": city,
        "country": country,
        "region": get_region(country),
        "lat": lat,
        "lng": lng,
        "precision": precision,
        "posts": posts_out,
    }


def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found. Run geocode.py first.")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        posts = json.load(f)

    print(f"\nLoaded {len(posts)} geocoded posts.")

    # -- Group by city+country ------------------------------------------
    groups = defaultdict(list)
    meta = {}  # key -> (city, country, precision, lat, lng)

    for post in posts:
        city = (post.get("city") or "").strip()
        country = (post.get("country") or "").strip()
        key = normalize_key(city, country)
        groups[key].append(post)
        if key not in meta:
            meta[key] = (city, country, post.get("precision"), post.get("lat"), post.get("lng"))

    # -- Build output locations -----------------------------------------
    locations = []
    for key, posts_group in groups.items():
        city, country, precision, lat, lng = meta[key]
        # Drop entries with no specific named place (city is empty)
        if not city:
            print(f"  Skipping (no city name): country={country!r}, {len(posts_group)} post(s)")
            continue
        # Use 'is None' so that lng=0.0 (prime meridian) is not treated as missing
        if lat is None or lng is None:
            print(f"  Skipping (no coords): {city}, {country}")
            continue
        loc = build_location(city, country, precision, lat, lng, posts_group)
        locations.append(loc)

    # Sort by total upvotes descending
    locations.sort(key=lambda l: sum(p["upvotes"] for p in l["posts"]), reverse=True)

    # -- Save ----------------------------------------------------------
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(locations, f, ensure_ascii=False, indent=2)

    print(f"\nDone: Merged {len(posts)} posts into {len(locations)} unique locations.")
    print(f"  Saved to {OUTPUT_FILE}\n")

    # -- Top 10 by total upvotes ----------------------------------------
    print("Top 10 locations by total post upvotes:")
    print("-" * 50)
    for i, loc in enumerate(locations[:10], 1):
        total = sum(p["upvotes"] for p in loc["posts"])
        post_count = len(loc["posts"])
        print(f"  {i:2}. {loc['city']}, {loc['country']:<20} {total:>6} upvotes  ({post_count} post{'s' if post_count != 1 else ''})")


if __name__ == "__main__":
    main()
