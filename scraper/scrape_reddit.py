"""
Step 1: Scrape Reddit posts about living in specific places.

Pulls from multiple subreddits and multiple sort orders to maximize coverage.
Deduplicates by post ID — comments are never fetched twice for the same post.

Output: data/raw/posts.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# -- Paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "scraper" / "data" / "raw"
OUTPUT_FILE = DATA_DIR / "posts.json"

# -- Constants ---------------------------------------------------------
USER_AGENT = "HowIsLivingThere/1.0 (data visualization project)"
REQUEST_DELAY = 2       # seconds between every request
POSTS_PER_PAGE = 100
MIN_COMMENT_LEN = 100   # raised from 80 for higher quality
MIN_COMMENT_SCORE = 5
MAX_COMMENTS_PER_POST = 50
BOT_AUTHORS = {"automoderator", "bot", "auto_moderator"}

# Subreddits to scrape and which sort orders to hit for each.
# (subreddit, sort, time_filter)  — time_filter only applies to "top"
SOURCES = [
    # Primary sub — all sorts
    ("howislivingthere", "top",  "all"),
    ("howislivingthere", "top",  "year"),
    ("howislivingthere", "top",  "month"),
    ("howislivingthere", "hot",  None),
    ("howislivingthere", "new",  None),
    # Additional subs — top-of-all-time + hot
    ("expats",              "top", "all"),
    ("expats",              "hot", None),
    ("digitalnomad",        "top", "all"),
    ("digitalnomad",        "hot", None),
    ("SameGrassButGreener", "top", "all"),
    ("SameGrassButGreener", "hot", None),
    ("AskACountry",         "top", "all"),
    ("AskACountry",         "hot", None),
]


def make_headers():
    return {"User-Agent": USER_AGENT}


def fetch_json(url, params=None, retries=3):
    """GET a URL and return parsed JSON, retrying on failure."""
    attempt = 0
    while attempt < retries:
        try:
            resp = requests.get(url, params=params, headers=make_headers(), timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            attempt += 1
            print(f"  HTTP error (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(5 * attempt)
    return None


def fetch_posts_for_source(subreddit, sort, time_filter, known_ids):
    """Paginate one (subreddit, sort, time_filter) combination.

    Returns list of new post dicts (no comments yet).
    Skips post IDs already in known_ids.
    """
    base_url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
    new_posts = []
    skipped = 0
    after = None
    page = 1

    while True:
        params = {"limit": POSTS_PER_PAGE}
        if time_filter:
            params["t"] = time_filter
        if after:
            params["after"] = after

        data = fetch_json(base_url, params=params)
        time.sleep(REQUEST_DELAY)

        if data is None:
            print(f"  Failed to fetch page {page} — stopping.")
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            p = child.get("data", {})
            post_id = p.get("id")
            if not post_id:
                continue
            if post_id in known_ids:
                skipped += 1
                continue
            known_ids.add(post_id)  # mark immediately to avoid cross-source dupes
            new_posts.append({
                "id": post_id,
                "subreddit": subreddit,
                "title": p.get("title", "").strip(),
                "score": p.get("score", 0),
                "url": p.get("url", ""),
                "permalink": "https://www.reddit.com" + p.get("permalink", ""),
                "num_comments": p.get("num_comments", 0),
                "created_utc": p.get("created_utc", 0),
                "thumbnail": p.get("thumbnail") if p.get("thumbnail") not in ("self", "default", "nsfw", "") else None,
                "comments": [],
            })

        after = data.get("data", {}).get("after")
        label = f"r/{subreddit} {sort}" + (f"/{time_filter}" if time_filter else "")
        print(f"  {label} page {page}: {len(new_posts)} new, {skipped} skipped")

        if not after:
            break
        page += 1

    return new_posts


def is_valid_comment(c):
    """Return True if a comment passes quality filters."""
    if c.get("stickied"):
        return False
    author = (c.get("author") or "").lower()
    if author in BOT_AUTHORS or author.endswith("bot"):
        return False
    body = c.get("body", "")
    if not body or body in ("[deleted]", "[removed]"):
        return False
    if len(body) < MIN_COMMENT_LEN:
        return False
    if c.get("score", 0) < MIN_COMMENT_SCORE:
        return False
    return True


def fetch_comments(post_id, subreddit, post_title):
    """Fetch and filter top comments for a post."""
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    data = fetch_json(url, params={"sort": "top", "limit": 200})
    time.sleep(REQUEST_DELAY)

    if data is None or not isinstance(data, list) or len(data) < 2:
        print(f"  Could not fetch comments for: {post_title[:60]}")
        return []

    comments_listing = data[1].get("data", {}).get("children", [])
    qualifying = []

    for child in comments_listing:
        if child.get("kind") != "t1":
            continue
        c = child.get("data", {})
        if not is_valid_comment(c):
            continue
        qualifying.append({
            "id": c.get("id"),
            "body": c.get("body", "").strip(),
            "score": c.get("score", 0),
            "author": c.get("author", ""),
        })
        if len(qualifying) >= MAX_COMMENTS_PER_POST:
            break

    return qualifying


def main():
    parser = argparse.ArgumentParser(description="Scrape Reddit posts about living in specific places.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch comments for ALL posts to update scores",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # -- Load existing data --------------------------------------------
    existing_posts = []
    known_ids = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing_posts = json.load(f)
        known_ids = {p["id"] for p in existing_posts}
        print(f"Loaded {len(existing_posts)} existing posts from {OUTPUT_FILE.name}.")

    # -- Fetch post listings across all sources -----------------------
    all_new_posts = []
    for subreddit, sort, time_filter in SOURCES:
        label = f"r/{subreddit} {sort}" + (f"/{time_filter}" if time_filter else "")
        print(f"\nFetching {label}...")
        new = fetch_posts_for_source(subreddit, sort, time_filter, known_ids)
        print(f"  -> {len(new)} new posts from {label}")
        all_new_posts.extend(new)

    print(f"\nTotal new posts across all sources: {len(all_new_posts)}")

    # -- Fetch comments ------------------------------------------------
    if args.refresh:
        targets = existing_posts + all_new_posts
        print(f"\n--refresh: re-fetching comments for all {len(targets)} posts...")
        for i, post in enumerate(targets, 1):
            sub = post.get("subreddit", "howislivingthere")
            print(f"[{i}/{len(targets)}] {post['title'][:70]}...")
            post["comments"] = fetch_comments(post["id"], sub, post["title"])
            print(f"  -> {len(post['comments'])} qualifying comment(s)")
        merged = targets
    else:
        if all_new_posts:
            print(f"\nFetching comments for {len(all_new_posts)} new posts...")
            for i, post in enumerate(all_new_posts, 1):
                sub = post.get("subreddit", "howislivingthere")
                print(f"[{i}/{len(all_new_posts)}] [{sub}] {post['title'][:65]}...")
                post["comments"] = fetch_comments(post["id"], sub, post["title"])
                print(f"  -> {len(post['comments'])} qualifying comment(s)")
        else:
            print("No new posts — nothing to fetch.")
        merged = existing_posts + all_new_posts

    # -- Save ----------------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {len(merged)} posts saved to {OUTPUT_FILE}")
    print(f"  ({len(all_new_posts)} new this run, {len(existing_posts)} pre-existing)")


if __name__ == "__main__":
    main()
