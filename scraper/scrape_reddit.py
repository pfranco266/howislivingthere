"""
Step 1: Scrape r/howislivingthere using Reddit's public JSON endpoints.
No OAuth required -- just a descriptive User-Agent header.

Supports incremental updates: only fetches comments for posts not already
in posts.json. Use --refresh to re-fetch comments for all posts (updates scores).

Output: data/raw/posts.json
"""

import argparse
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
    """GET a URL and return parsed JSON, with retry on failure.

    429 rate-limit responses wait and retry without burning a retry slot --
    Reddit throttles fresh connections heavily but eventually lets through.
    """
    attempt = 0
    while attempt < retries:
        try:
            resp = requests.get(url, params=params, headers=make_headers(), timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"  Rate limited -- waiting {wait}s...")
                time.sleep(wait)
                continue  # don't increment attempt; rate limits aren't failures
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            attempt += 1
            print(f"  HTTP error (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(5 * attempt)
    return None


def fetch_all_posts(known_ids=None):
    """Paginate through top posts and return (new_posts, skipped_count).

    Continues paginating even when encountering known posts -- new posts can
    appear between old ones due to score changes reshuffling the ranking.
    """
    if known_ids is None:
        known_ids = set()

    new_posts = []
    skipped_count = 0
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
            post_id = p.get("id")

            if post_id in known_ids:
                skipped_count += 1
                continue

            post = {
                "id": post_id,
                "title": p.get("title", "").strip(),
                "score": p.get("score", 0),
                "url": p.get("url", ""),
                "permalink": "https://www.reddit.com" + p.get("permalink", ""),
                "num_comments": p.get("num_comments", 0),
                "created_utc": p.get("created_utc", 0),
                "thumbnail": p.get("thumbnail") if p.get("thumbnail") not in ("self", "default", "nsfw", "") else None,
                "comments": [],
            }
            new_posts.append(post)

        after = data.get("data", {}).get("after")
        print(f"Fetched page {page} ({len(new_posts)} new, {skipped_count} skipped)...")

        if not after:
            print("No more pages -- reached end of subreddit.")
            break

        page += 1

    return new_posts, skipped_count


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
    parser = argparse.ArgumentParser(description="Scrape r/howislivingthere posts and comments.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch comments for ALL posts to update scores (still won't duplicate posts)",
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

    # -- Fetch post listings (paginate fully, skip known IDs) ----------
    print(f"\nFetching posts from r/{SUBREDDIT} (top of all time)...")
    new_posts, skipped_count = fetch_all_posts(known_ids)
    print(f"\nFound {len(new_posts)} new posts, {skipped_count} already scraped (skipped).")

    # -- Fetch comments ------------------------------------------------
    if args.refresh:
        # Re-fetch comments for every post (new + existing) to update scores
        all_posts = existing_posts + new_posts
        print(f"\n--refresh: re-fetching comments for all {len(all_posts)} posts...")
        for i, post in enumerate(all_posts, 1):
            print(f"[{i}/{len(all_posts)}] {post['title'][:70]}...")
            post["comments"] = fetch_comments(post["id"], post["title"])
            print(f"  -> {len(post['comments'])} qualifying comment(s)")
        merged = all_posts
    else:
        if new_posts:
            print(f"\nFetching comments for {len(new_posts)} new posts...")
            for i, post in enumerate(new_posts, 1):
                print(f"[{i}/{len(new_posts)}] {post['title'][:70]}...")
                post["comments"] = fetch_comments(post["id"], post["title"])
                print(f"  -> {len(post['comments'])} qualifying comment(s)")
        else:
            print("No new posts -- nothing to fetch.")
        merged = existing_posts + new_posts

    # -- Save ----------------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved {len(merged)} posts to {OUTPUT_FILE}")
    print(f"  ({len(new_posts)} new this run, {len(existing_posts)} pre-existing)")


if __name__ == "__main__":
    main()
