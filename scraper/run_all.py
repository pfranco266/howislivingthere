"""
Convenience runner: executes the full 4-step pipeline in sequence.

Usage:
  python run_all.py                # incremental: only fetches new posts + comments
  python run_all.py --skip-scrape  # skip step 1 (use existing posts.json)
  python run_all.py --refresh      # re-fetch comments for ALL posts to update scores
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRAPER_DIR = PROJECT_ROOT / "scraper"
DATA_DIR = SCRAPER_DIR / "data" / "raw"
SRC_DATA = PROJECT_ROOT / "src" / "data" / "locations.json"
POSTS_FILE = DATA_DIR / "posts.json"

PYTHON = sys.executable

STEPS = [
    {
        "name": "Scraping Reddit",
        "script": SCRAPER_DIR / "scrape_reddit.py",
        "output": DATA_DIR / "posts.json",
        "skippable": True,
        "pass_refresh": True,
    },
    {
        "name": "Parsing Locations (Claude API)",
        "script": SCRAPER_DIR / "parse_locations.py",
        "output": DATA_DIR / "parsed_locations.json",
        "skippable": False,
        "pass_refresh": False,
    },
    {
        "name": "Geocoding",
        "script": SCRAPER_DIR / "geocode.py",
        "output": DATA_DIR / "geocoded.json",
        "skippable": False,
        "pass_refresh": False,
    },
    {
        "name": "Merging Output",
        "script": SCRAPER_DIR / "merge_output.py",
        "output": SRC_DATA,
        "skippable": False,
        "pass_refresh": False,
    },
]


SEP = "=" * 55


def read_post_ids(path):
    """Return set of post IDs from a posts.json file, or empty set if missing."""
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        posts = json.load(f)
    return {p["id"] for p in posts}


def read_location_ids(path):
    """Return set of location IDs from a locations.json file, or empty set if missing."""
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        locations = json.load(f)
    return {loc["id"] for loc in locations}


def run_step(step, step_num, total, refresh=False):
    print(f"\n{SEP}")
    print(f"  Step {step_num}/{total}: {step['name']}")
    print(f"{SEP}\n")

    cmd = [PYTHON, str(step["script"])]
    if refresh and step.get("pass_refresh"):
        cmd.append("--refresh")

    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        print(f"\nFAILED: Step {step_num} exited with code {result.returncode}.")
        sys.exit(result.returncode)

    if not step["output"].exists():
        print(f"\nFAILED: Step {step_num} completed but expected output not found: {step['output']}")
        sys.exit(1)

    print(f"\nOK: Step {step_num} complete. Output: {step['output']}")


def print_summary(post_ids_before, location_ids_before, start_time):
    """Read final output files and print a run summary."""
    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)

    post_ids_after = read_post_ids(POSTS_FILE)
    new_posts_count = len(post_ids_after - post_ids_before)
    total_posts = len(post_ids_after)

    locations_after = []
    if SRC_DATA.exists():
        with open(SRC_DATA, encoding="utf-8") as f:
            locations_after = json.load(f)

    location_ids_after = {loc["id"] for loc in locations_after}
    new_locations_count = len(location_ids_after - location_ids_before)
    total_locations = len(locations_after)

    print(f"\n{SEP}")
    print(f"  Pipeline complete in {mins}m {secs}s")
    print(f"{SEP}")
    print(f"  New posts added this run : {new_posts_count}")
    print(f"  Total posts in dataset   : {total_posts}")
    print(f"  New locations added      : {new_locations_count}")
    print(f"  Total unique locations   : {total_locations}")
    print(f"  Output: {SRC_DATA}")
    print(f"{SEP}\n")


def main():
    parser = argparse.ArgumentParser(description="Run the full howislivingthere scraper pipeline.")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip step 1 (scraping Reddit) -- use existing posts.json",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch comments for ALL posts to update scores (passed to scrape_reddit.py)",
    )
    args = parser.parse_args()

    start_time = time.time()

    # Snapshot state before the run so we can report what changed
    post_ids_before = read_post_ids(POSTS_FILE)
    location_ids_before = read_location_ids(SRC_DATA)

    active_steps = []
    for step in STEPS:
        if step["skippable"] and args.skip_scrape:
            print(f"\nSkipping step (--skip-scrape): {step['name']}")
            if not step["output"].exists():
                print(f"  Warning: {step['output']} does not exist -- downstream steps may fail.")
            continue
        active_steps.append(step)

    total = len(active_steps)
    for i, step in enumerate(active_steps, 1):
        run_step(step, i, total, refresh=args.refresh)

    print_summary(post_ids_before, location_ids_before, start_time)


if __name__ == "__main__":
    main()
