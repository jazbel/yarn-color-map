import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.hobbii import HobbiiScraper
from scrapers.lovecrafts import LovecraftsScraper
from scrapers.knitpicks import KnitPicksScraper
from yarn_meta import WEIGHT_ORDER, FIBER_ORDER

app = FastAPI(title="Yarn Color Map")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRAPERS = {
    "hobbii": HobbiiScraper(),
    "lovecrafts": LovecraftsScraper(),
    "knitpicks": KnitPicksScraper(),
}

CACHE_PATH = Path(__file__).parent / "yarn_cache.json"

COLOR_FAMILIES = ["red", "pink", "orange", "yellow", "green", "teal", "blue", "purple", "gray", "white", "black"]


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def save_cache(data: dict) -> None:
    CACHE_PATH.write_text(json.dumps(data, indent=2))


@app.get("/api/stores")
def get_stores():
    return [
        {"id": sid, "name": scraper.name}
        for sid, scraper in SCRAPERS.items()
    ]


@app.get("/api/color-families")
def get_color_families():
    return COLOR_FAMILIES

@app.get("/api/weights")
def get_weights():
    return WEIGHT_ORDER

@app.get("/api/fibers")
def get_fibers():
    return FIBER_ORDER


@app.get("/api/yarns")
async def get_yarns(
    store: Optional[str] = None,
    color_family: Optional[str] = None,
    weight: Optional[str] = None,
    fiber: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=60, le=10000),
    offset: int = 0,
):
    cache = load_cache()
    store_ids = [store] if store and store in SCRAPERS else list(SCRAPERS.keys())

    # Scrape any store not yet cached (scrape sequentially to avoid hammering
    # multiple CDNs simultaneously)
    for sid in [s for s in store_ids if s not in cache]:
        yarns = await SCRAPERS[sid].scrape()
        cache[sid] = yarns
        save_cache(cache)

    all_yarns = [yarn for sid in store_ids for yarn in cache.get(sid, [])]

    if color_family:
        all_yarns = [y for y in all_yarns if y.get("color_family") == color_family]

    if weight:
        all_yarns = [y for y in all_yarns if y.get("weight") == weight]

    if fiber:
        all_yarns = [y for y in all_yarns if y.get("fiber") == fiber]

    if search:
        q = search.lower()
        all_yarns = [
            y for y in all_yarns
            if q in y.get("product_name", "").lower()
            or q in y.get("color_name", "").lower()
        ]

    return {
        "total": len(all_yarns),
        "offset": offset,
        "limit": limit,
        "items": all_yarns[offset: offset + limit],
    }


@app.post("/api/refresh")
async def refresh(store: Optional[str] = None):
    cache = load_cache()
    store_ids = [store] if store and store in SCRAPERS else list(SCRAPERS.keys())
    results = await asyncio.gather(*[SCRAPERS[sid].scrape() for sid in store_ids])
    for sid, yarns in zip(store_ids, results):
        cache[sid] = yarns
    save_cache(cache)
    total = sum(len(v) for v in cache.values())
    return {"refreshed": store_ids, "total_yarns": total}


@app.delete("/api/cache")
def clear_cache():
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
    return {"cleared": True}


# Serve the frontend from the project root
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
