"""
Step 2: Parse city/country from post titles using Claude API.
Batches titles in groups of 15 to minimise API calls.

Input:  data/raw/posts.json
Output: data/raw/parsed_locations.json
"""

import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import anthropic
from dotenv import load_dotenv

# -- Paths & env -------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "scraper" / "data" / "raw"
INPUT_FILE = DATA_DIR / "posts.json"
OUTPUT_FILE = DATA_DIR / "parsed_locations.json"

load_dotenv(PROJECT_ROOT / ".env")

# -- Constants ---------------------------------------------------------
MODEL = "claude-sonnet-4-20250514"
BATCH_SIZE = 15
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds

SYSTEM_PROMPT = """You are a location extraction tool. For each Reddit post title, extract the geographic location being discussed.
Return a JSON array with one object per title, in the same order as the input. Each object should have:

"city": The specific city or area name, or null if not determinable
"country": The country name, or null if not determinable
"precision": One of "city", "region", or "country"

"city" = specific city (e.g., "Lisbon, Portugal")
"region" = broader area (e.g., "rural Japan", "the Bay Area", "Southern France")
"country" = just a country with no specifics (e.g., "How is living in Japan?")

Rules:
- If the title contains a clear city name, use it. "How is living in Porto, Portugal?" -> {"city": "Porto", "country": "Portugal", "precision": "city"}
- For metro areas, use the main city. "Seattle area" -> {"city": "Seattle", "country": "United States", "precision": "region"}
- For vague regions, describe them. "Rural Japan" -> {"city": "Rural Japan", "country": "Japan", "precision": "region"}
- If the title is just an image with no location text, or you truly cannot determine any location, return {"city": null, "country": null, "precision": null}
- Use English country names. Use the most common English city name.
- Do NOT guess if uncertain -- return null fields instead.

Return ONLY the JSON array, no other text."""


def parse_batch(client, titles, batch_num, total_batches):
    """Send a batch of titles to Claude and return parsed location list."""
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    user_message = f"Extract locations from these post titles:\n{numbered}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)

            if not isinstance(parsed, list) or len(parsed) != len(titles):
                raise ValueError(
                    f"Expected {len(titles)} items, got {len(parsed) if isinstance(parsed, list) else type(parsed)}"
                )

            return parsed

        except anthropic.AuthenticationError:
            print("  Error: ANTHROPIC_API_KEY is missing or invalid. Check your .env file.")
            sys.exit(1)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  Batch {batch_num}/{total_batches} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
        except anthropic.APIError as e:
            # Log status code only -- never log response body which may echo back input
            print(f"  Batch {batch_num}/{total_batches} attempt {attempt}/{MAX_RETRIES} API error (status {e.status_code})")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)

    print(f"  Batch {batch_num}/{total_batches} failed after {MAX_RETRIES} attempts -- filling with nulls.")
    return [{"city": None, "country": None, "precision": None}] * len(titles)


def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found. Run scrape_reddit.py first.")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        posts = json.load(f)

    print(f"\nLoaded {len(posts)} posts.")

    client = anthropic.Anthropic(api_key=api_key)

    # -- Batch titles --------------------------------------------------
    titles = [p["title"] for p in posts]
    batches = [titles[i: i + BATCH_SIZE] for i in range(0, len(titles), BATCH_SIZE)]
    total_batches = len(batches)

    print(f"Parsing {len(titles)} titles in {total_batches} batch(es) of up to {BATCH_SIZE}...\n")

    all_parsed = []

    for batch_num, batch in enumerate(batches, 1):
        print(f"Parsing batch {batch_num}/{total_batches}...")
        results = parse_batch(client, batch, batch_num, total_batches)
        for title, loc in zip(batch, results):
            city = loc.get("city")
            country = loc.get("country")
            precision = loc.get("precision")
            if city or country:
                label = f"{city}, {country}" if city and country else (city or country)
                print(f"  Parsed: {label} ({precision})")
            else:
                print(f"  Skipped (no location): {title[:70]}")
        all_parsed.extend(results)

    # -- Merge with post data ------------------------------------------
    results_with_posts = []
    skipped = 0

    for post, loc in zip(posts, all_parsed):
        city = loc.get("city")
        country = loc.get("country")

        if not city and not country:
            print(f"Skipped: {post['title'][:80]}")
            skipped += 1
            continue

        results_with_posts.append({
            **post,
            "city": city,
            "country": country,
            "precision": loc.get("precision"),
        })

    # -- Save ----------------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results_with_posts, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Parsed {len(results_with_posts)} posts with locations.")
    print(f"  Skipped {skipped} posts (no location found).")
    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
