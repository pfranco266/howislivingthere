"""
Step 1: Scrape r/howislivingthere using Reddit's public JSON endpoints.
No OAuth required -- just a descriptive User-Agent header.

Output: data/raw/posts.json
"""

import json
import sys
import time
from pathlib import Path

import requests

# Windows terminals default to cp1252; post titles contain non-ASCII chars.
# Replace unencodable characters with '?' rather than crashing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# -- Paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "scraper" / "data" / "raw"
OUTPUT_FILE = DATA_DIR / "posts.json"

# -- Constants ---------------------------------------------------------
SUBREDDIT = "howislivingthere"
USER_AGENT = "HowIsLivingThere/1.0 (data visualization project)"
POSTS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/top.json"
COMMENTS_URL = "https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
REQUEST_DELAY = 2      # seconds between every request
POSTS_PER_PAGE = 100
MIN_COMMENT_LEN = 80
MIN_COMMENT_SCORE = 5
MAX_COMMENTS_PER_POST = 50
BOT_AUTHORS = {"automoderator", "bot", "auto_moderator"}


def make_headers():
    return {"User-Agent": USER_AGENT}


def fetch_json(url, params=None, retries=3):
    """GET a URL and return parsed JSON, with retry on failure."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, headers=make_headers(), timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"  Rate limited -- waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"  HTTP error (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(5 * attempt)
    return None


def fetch_all_posts():
    """Paginate through top posts and return list of raw post dicts."""
    posts = []
    after = None
    page = 1

    while True:
        params = {"t": "all", "limit": POSTS_PER_PAGE}
        if after:
            params["after"] = after

        data = fetch_json(POSTS_URL, params=params)
        time.sleep(REQUEST_DELAY)

        if data is None:
            print(f"  Failed to fetch page {page}, stopping pagination.")
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            p = child.get("data", {})
            post = {
                "id": p.get("id"),
                "title": p.get("title", "").strip(),
                "score": p.get("score", 0),
                "url": p.get("url", ""),
                "permalink": "https://www.reddit.com" + p.get("permalink", ""),
                "num_comments": p.get("num_comments", 0),
                "created_utc": p.get("created_utc", 0),
                "thumbnail": p.get("thumbnail") if p.get("thumbnail") not in ("self", "default", "nsfw", "") else None,
                "comments": [],
            }
            posts.append(post)

        after = data.get("data", {}).get("after")
        print(f"Fetched page {page} ({len(posts)} posts total)...")

        if not after:
            print("No more pages -- reached end of subreddit.")
            break

        page += 1

    return posts


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


def fetch_comments(post_id, post_title):
    """Fetch and filter top comments for a post."""
    url = COMMENTS_URL.format(subreddit=SUBREDDIT, post_id=post_id)
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # -- Check if output already exists --------------------------------
    if OUTPUT_FILE.exists():
        answer = input(f"\n{OUTPUT_FILE} already exists. Re-scrape? [y/N]: ").strip().lower()
        if answer != "y":
            print("Skipping scrape -- using existing data.")
            return

    # -- Fetch posts ----------------------------------------------------
    print(f"\nFetching posts from r/{SUBREDDIT} (top of all time)...")
    posts = fetch_all_posts()
    print(f"\nFetched {len(posts)} posts total.")

    # -- Fetch comments for each post -----------------------------------
    print("\nFetching comments for each post...")
    for i, post in enumerate(posts, 1):
        print(f"[{i}/{len(posts)}] Fetching comments for: {post['title'][:70]}...")
        post["comments"] = fetch_comments(post["id"], post["title"])
        print(f"  -> {len(post['comments'])} qualifying comment(s)")

    # -- Save output ----------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved {len(posts)} posts to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
