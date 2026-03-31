"""
Step 3: Geocode city+country pairs using Nominatim (free, no API key).
Caches results to avoid re-geocoding on subsequent runs.

Input:  data/raw/parsed_locations.json
Output: data/raw/geocoded.json
Cache:  data/raw/geocode_cache.json
"""

import json
import sys
import time
from pathlib import Path

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# -- Paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "scraper" / "data" / "raw"
INPUT_FILE = DATA_DIR / "parsed_locations.json"
OUTPUT_FILE = DATA_DIR / "geocoded.json"
CACHE_FILE = DATA_DIR / "geocode_cache.json"

# -- Constants ---------------------------------------------------------
REQUEST_DELAY = 1.5   # Nominatim requires ≤1 req/sec; 1.5s adds buffer
MAX_RETRIES = 3

# -- Manual overrides for known bad Nominatim results ------------------
# Key format: "city_lowercase|country_lowercase" (same as cache_key())
MANUAL_OVERRIDES = {
    "falkland islands|falkland islands": {"lat": -51.796, "lng": -59.524},
    "falkland islands|united kingdom":   {"lat": -51.796, "lng": -59.524},
    "southwest egypt|egypt":             {"lat": 23.0,    "lng": 28.0},
}
USER_AGENT = "HowIsLivingThere/1.0 (data visualization project)"


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cache_key(city, country):
    return f"{(city or '').lower().strip()}|{(country or '').lower().strip()}"


def geocode_query(geolocator, query):
    """Geocode a query string, retrying on transient failures."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            location = geolocator.geocode(query, timeout=10)
            time.sleep(REQUEST_DELAY)
            return location
        except GeocoderTimedOut:
            print(f"  Timeout (attempt {attempt}/{MAX_RETRIES}) for: {query}")
            time.sleep(REQUEST_DELAY * attempt)
        except GeocoderServiceError as e:
            print(f"  Service error (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(REQUEST_DELAY * attempt)
    return None


def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found. Run parse_locations.py first.")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        posts = json.load(f)

    print(f"\nLoaded {len(posts)} parsed posts.")

    cache = load_cache()

    # -- Apply manual overrides to cache (always wins) -----------------
    for override_key, coords in MANUAL_OVERRIDES.items():
        if cache.get(override_key) != coords:
            print(f"  Applying manual override: {override_key} -> {coords}")
            cache[override_key] = coords
    save_cache(cache)

    geolocator = Nominatim(user_agent=USER_AGENT)

    # -- Collect unique city+country pairs -----------------------------
    unique_pairs = {}
    for p in posts:
        key = cache_key(p.get("city"), p.get("country"))
        if key not in unique_pairs:
            unique_pairs[key] = (p.get("city"), p.get("country"))

    print(f"Found {len(unique_pairs)} unique city+country pairs.")
    uncached = [v for k, v in unique_pairs.items() if k not in cache]
    print(f"Need to geocode {len(uncached)} (rest are cached).\n")

    # -- Geocode uncached pairs -----------------------------------------
    for city, country in uncached:
        key = cache_key(city, country)
        # Skip if a manual override already set this key
        if key in MANUAL_OVERRIDES:
            continue
        query_full = f"{city}, {country}" if city and country else (city or country)
        query_country = country or city

        location = geocode_query(geolocator, query_full)

        if location:
            lat = round(location.latitude, 4)
            lng = round(location.longitude, 4)
            print(f"Geocoding: {query_full} -> {lat}, {lng}")
            cache[key] = {"lat": lat, "lng": lng}
        else:
            # Fallback: try just the country
            print(f"  Primary query failed, trying fallback: {query_country}")
            location = geocode_query(geolocator, query_country)
            if location:
                lat = round(location.latitude, 4)
                lng = round(location.longitude, 4)
                print(f"  Fallback succeeded: {query_country} -> {lat}, {lng}")
                cache[key] = {"lat": lat, "lng": lng}
            else:
                print(f"  FAIL: Could not geocode: {query_full} -- skipping")
                cache[key] = None

        save_cache(cache)

    # -- Attach coords to posts -----------------------------------------
    geocoded_posts = []
    failed = []

    for post in posts:
        key = cache_key(post.get("city"), post.get("country"))
        coords = cache.get(key)
        if coords:
            geocoded_posts.append({**post, "lat": coords["lat"], "lng": coords["lng"]})
        else:
            label = f"{post.get('city')}, {post.get('country')}"
            failed.append(label)

    if failed:
        unique_failed = sorted(set(failed))
        print(f"\nFAIL: Could not geocode {len(unique_failed)} unique location(s):")
        for loc in unique_failed:
            print(f"  - {loc}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geocoded_posts, f, ensure_ascii=False, indent=2)

    print(f"\nDone: Geocoded {len(geocoded_posts)} posts.")
    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
