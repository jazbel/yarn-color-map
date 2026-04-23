"""
Standalone scrape script — runs all store scrapers and writes yarn_cache.json.
Run before starting the server to pre-populate the cache.

    python3 scrape.py              # scrape all stores
    python3 scrape.py hobbii       # scrape one store
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.hobbii import HobbiiScraper
from scrapers.lovecrafts import LovecraftsScraper
from scrapers.knitpicks import KnitPicksScraper

SCRAPERS = {
    "hobbii": HobbiiScraper(),
    "lovecrafts": LovecraftsScraper(),
    "knitpicks": KnitPicksScraper(),
}

CACHE_PATH = Path(__file__).parent / "yarn_cache.json"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


async def run(store_ids: list[str]) -> None:
    cache = load_cache()

    for sid in store_ids:
        print(f"Scraping {SCRAPERS[sid].name}...", flush=True)
        yarns = await SCRAPERS[sid].scrape()
        cache[sid] = yarns
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
        print(f"  → {len(yarns)} yarns saved", flush=True)

    total = sum(len(v) for v in cache.values())
    print(f"\nDone. {total} total yarns in cache.")


if __name__ == "__main__":
    requested = sys.argv[1:] if len(sys.argv) > 1 else []
    ids = []
    for s in requested:
        if s in SCRAPERS:
            ids.append(s)
        else:
            print(f"Unknown store '{s}'. Valid: {', '.join(SCRAPERS)}")
            sys.exit(1)
    if not ids:
        ids = list(SCRAPERS.keys())

    asyncio.run(run(ids))
