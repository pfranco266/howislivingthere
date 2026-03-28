"""
Convenience runner: executes the full 4-step pipeline in sequence.

Usage:
  python run_all.py                # run all 4 steps
  python run_all.py --skip-scrape  # skip step 1 (use existing posts.json)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRAPER_DIR = PROJECT_ROOT / "scraper"
DATA_DIR = SCRAPER_DIR / "data" / "raw"
SRC_DATA = PROJECT_ROOT / "src" / "data" / "locations.json"

PYTHON = sys.executable

STEPS = [
    {
        "name": "Scraping Reddit",
        "script": SCRAPER_DIR / "scrape_reddit.py",
        "output": DATA_DIR / "posts.json",
        "skippable": True,
    },
    {
        "name": "Parsing Locations (Claude API)",
        "script": SCRAPER_DIR / "parse_locations.py",
        "output": DATA_DIR / "parsed_locations.json",
        "skippable": False,
    },
    {
        "name": "Geocoding",
        "script": SCRAPER_DIR / "geocode.py",
        "output": DATA_DIR / "geocoded.json",
        "skippable": False,
    },
    {
        "name": "Merging Output",
        "script": SCRAPER_DIR / "merge_output.py",
        "output": SRC_DATA,
        "skippable": False,
    },
]


SEP = "=" * 55


def run_step(step, step_num, total):
    print(f"\n{SEP}")
    print(f"  Step {step_num}/{total}: {step['name']}")
    print(f"{SEP}\n")

    result = subprocess.run([PYTHON, str(step["script"])], check=False)

    if result.returncode != 0:
        print(f"\nFAILED: Step {step_num} exited with code {result.returncode}.")
        sys.exit(result.returncode)

    if not step["output"].exists():
        print(f"\nFAILED: Step {step_num} completed but expected output not found: {step['output']}")
        sys.exit(1)

    print(f"\nOK: Step {step_num} complete. Output: {step['output']}")


def main():
    parser = argparse.ArgumentParser(description="Run the full howislivingthere scraper pipeline.")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip step 1 (scraping Reddit) -- use existing posts.json",
    )
    args = parser.parse_args()

    start_time = time.time()

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
        run_step(step, i, total)

    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)
    print(f"\n{SEP}")
    print(f"  Pipeline complete in {mins}m {secs}s")
    print(f"  Output: {SRC_DATA}")
    print(f"{SEP}\n")


if __name__ == "__main__":
    main()
