"""
Standalone scrape script — runs all store scrapers and writes yarn_cache.json.
Run before starting the server to pre-populate the cache.

    python3 scrape.py              # scrape all stores
    python3 scrape.py hobbii       # scrape one store
    python3 scrape.py --force      # re-scrape even if images are already saved
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.hobbii import HobbiiScraper
from scrapers.lionbrand import LionBrandScraper
from scrapers.knitpicks import KnitPicksScraper
from scrapers.michaels import MichaelsScraper
from scrapers.knittingforolive import KnittingForOliveScraper

SCRAPERS = {
    "hobbii": HobbiiScraper(),
    "lionbrand": LionBrandScraper(),
    "knitpicks": KnitPicksScraper(),
    "michaels": MichaelsScraper(),
    "knittingforolive": KnittingForOliveScraper(),
}

CACHE_PATH = Path(__file__).parent / "yarn_cache.json"
IMAGES_DIR = Path(__file__).parent / "images"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def images_saved(cache: dict, store_id: str) -> bool:
    """Return True if this store has been scraped and at least one image file exists on disk."""
    yarns = cache.get(store_id, [])
    if not yarns:
        return False
    for yarn in yarns:
        local_path = yarn.get("local_image_path")
        if local_path and (IMAGES_DIR / Path(local_path).name).exists():
            return True
    return False


async def run(store_ids: list[str], force: bool = False) -> None:
    cache = load_cache()

    for sid in store_ids:
        if not force and images_saved(cache, sid):
            count = len(cache.get(sid, []))
            print(f"Skipping {SCRAPERS[sid].name} ({count} yarns already cached with local images)", flush=True)
            continue
        print(f"Scraping {SCRAPERS[sid].name}...", flush=True)
        yarns = await SCRAPERS[sid].scrape()
        cache[sid] = yarns
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
        print(f"  → {len(yarns)} yarns saved", flush=True)

    total = sum(len(v) for v in cache.values())
    print(f"\nDone. {total} total yarns in cache.")


if __name__ == "__main__":
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]

    ids = []
    for s in args:
        if s in SCRAPERS:
            ids.append(s)
        else:
            print(f"Unknown store '{s}'. Valid: {', '.join(SCRAPERS)}")
            sys.exit(1)
    if not ids:
        ids = list(SCRAPERS.keys())

    asyncio.run(run(ids, force=force))
