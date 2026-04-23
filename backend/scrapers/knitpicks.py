"""
Knit Picks scraper.

Uses the JSON-LD ProductGroup data embedded in each category page.
Every KnitPicks yarn category page embeds a <script type="application/ld+json">
block with a ProductGroup whose hasVariant array lists every colour variant,
complete with name, URL, and per-colour product image hosted on CloudFront.

Tier 1: Fetch category pages → parse JSON-LD hasVariant → PIL image extraction.
Tier 2: Color-name → hex fallback (used when all category pages are unreachable).
"""
import asyncio
import json as _json
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, HEADERS
from yarn_meta import infer_weight, infer_fiber

BATCH_SIZE = 20

_MULTICOLOR = {
    "rainbow","multi","variegat","ombre","gradient","speckl",
    "print","tweed","marled","stripe","tie-dye",
}

def _is_solid(name: str) -> bool:
    n = name.lower()
    return not any(kw in n for kw in _MULTICOLOR)

def _small_img(url: str) -> str:
    """Resize the CloudFront image to 300 px to save bandwidth."""
    if "~w=" in url:
        return url.split("~")[0] + "~w=300,h=300"
    return url


# ── Category pages that embed full colour-variant JSON-LD ─────────────────────
# (product_name, category_url, weight, fiber, price)
_CATEGORY_PAGES = [
    ("Palette Fingering",
     "https://www.knitpicks.com/yarn/palette-yarn/c/5420132",
     "Fingering", "Wool", "$2.79"),
    ("Wool of the Andes Worsted",
     "https://www.knitpicks.com/yarn/wool-of-the-andes-worsted-yarn/c/5420103",
     "Worsted", "Wool", "$5.49"),
    ("Comfy Worsted",
     "https://www.knitpicks.com/yarn/comfy-worsted-yarn/c/5420171",
     "Worsted", "Cotton", "$6.99"),
    ("Comfy Fingering",
     "https://www.knitpicks.com/yarn/comfy-fingering-yarn/c/5420197",
     "Fingering", "Cotton", "$5.49"),
    ("Stroll Yarn",
     "https://www.knitpicks.com/yarn/stroll-yarn/c/5420133",
     "Fingering", "Wool", "$4.99"),
    ("Brava Worsted",
     "https://www.knitpicks.com/yarn/brava-worsted-yarn/c/5420219",
     "Worsted", "Acrylic", "$4.99"),
    ("Swish Worsted",
     "https://www.knitpicks.com/yarn/swish-worsted-yarn/c/5420153",
     "Worsted", "Wool", "$5.99"),
    ("Dishie",
     "https://www.knitpicks.com/yarn/dishie-yarn/c/5420207",
     "Worsted", "Cotton", "$4.29"),
]

# ── Tier-2 seed data ──────────────────────────────────────────────────────────
_PALETTE = [
    "Bare","White","Swan","Cream","Ivory","Eggshell","Pearl","Blizzard",
    "Fog","Mist","Haze","Silver","Dove","Ash","Marble","Cobblestone",
    "Stone","Pebble","Graphite","Mineral","Shadow","Coal","Black",
    "Platinum","Smoke","Slate","Pewter","Storm","Iron",
    "Fairy Tale","Blush","Ballerina","Carnation","Rose","Ballet",
    "Flamingo","Calypso","Peony","Camellia","Amaranth","Cerise",
    "Fuchsia","Magenta","Mulberry","Berry","Beet","Cranberry",
    "Raspberry","Watermelon","Hot Pink","Deep Rose","Mauve",
    "Dusty Rose","Antique Rose","Vintage Rose",
    "Red","Scarlet","Ruby","Garnet","Cherry","Tomato","Fire","Cayenne",
    "Paprika","Cardinal","Crimson","Brick","Burgundy","Pomegranate",
    "Apricot","Peach","Melon","Cantaloupe","Papaya",
    "Tangerine","Tiger","Orange","Saffron","Pumpkin","Squash",
    "Rust","Copper","Sienna","Terracotta","Adobe","Clay","Burnt Sienna",
    "Canary","Daffodil","Lemon","Citron","Butter","Sunburst","Gold",
    "Goldenrod","Sungold","Maize","Straw","Wheat","Champagne",
    "Mustard","Ochre","Brass","Amber","Honey","Caramel","Toffee",
    "Chartreuse","Lime","Apple Green","Avocado","Celery",
    "Pistachio","Spearmint","Mint","Seafoam","Aloe","Sage","Fern",
    "Clover","Moss","Basil","Verdant","Meadow","Grass",
    "Kelly","Shamrock","Jade","Emerald","Forest","Conifer","Hunter",
    "Pine","Shire","Juniper","Spruce","Cedar","Bottle Green",
    "Aqua","Turquoise","Lagoon","Pool","Oasis","Surf",
    "Clarity","Teal","Fjord","Seas","Tide","Pacific","Atlantic",
    "Malachite","Aquamarine",
    "Powder Blue","Baby Blue","Sky","Carolina Blue",
    "Cornflower","Periwinkle","Wedgwood","Cerulean","Azure","Denim",
    "Cobalt","Marina","Neptune","Indigo","Baltic","Navy","Midnight",
    "Harbor","Royal Blue","Sapphire","Electric Blue","Hyacinth",
    "Delft","Colonial Blue","Cloud Blue","Steel Blue",
    "Lavender","Lilac","Wisteria","Iris","Orchid","Thistle",
    "Violet","Amethyst","Purple","Grape","Plum","Boysenberry",
    "Eggplant","Aubergine","Byzantium","Dusty Purple",
    "Almond","Birch","Tan","Sand","Camel","Fawn","Driftwood","Latte",
    "Mocha","Coffee","Espresso","Bark","Nutmeg","Cinnamon","Chestnut",
    "Walnut","Mahogany","Chocolate","Dark Brown",
]

_WOTA_COLORS = [
    "White","Cream","Bare","Pampas","Camel","Bison","Tan","Almond",
    "Chestnut","Hazelnut","Espresso","Bark","Claret","Garnet","Rouge",
    "Currant","Red","Pomegranate","Ginger","Pumpkin","Amber","Gold",
    "Canary","Mint","Jade","Moss","Forest","Hunter","Teal","Pool",
    "Cerulean","Sky Blue","Periwinkle","Cornflower","Delft","Navy",
    "Midnight","Indigo","Baltic","Iris","Amethyst","Wisteria","Mulberry",
    "Eggplant","Heather","Gray","Ash","Cobblestone","Charcoal","Black",
]

def _fallback_rows() -> list[tuple[str, str, str, str, str]]:
    rows = []
    for c in _PALETTE:
        rows.append(("Palette Fingering", c, "Fingering", "$2.79", "Wool"))
    for c in _WOTA_COLORS:
        rows.append(("Wool of the Andes Worsted", c, "Worsted", "$5.49", "Wool"))
    return rows


def _parse_variants(soup: BeautifulSoup) -> list[dict]:
    """Extract hasVariant list from JSON-LD ProductGroup on the page."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(tag.string or "")
            if "hasVariant" in data:
                return data["hasVariant"]
        except Exception:
            pass
    return []


class KnitPicksScraper(BaseScraper):
    store_id = "knitpicks"
    name = "Knit Picks"
    base_url = "https://www.knitpicks.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results = await self._jsonld_scrape(limit)
        if not results:
            results = await self._fallback(limit)
        return results

    # ── Tier 1: JSON-LD category pages ───────────────────────────────────────

    async def _jsonld_scrape(self, limit: int) -> list[dict[str, Any]]:
        """
        For each known category page, parse the embedded JSON-LD ProductGroup
        and build one yarn entry per colour variant.  Each variant has a real
        per-colour product image; PIL extracts the dominant hex from it.
        """
        results: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=30
            ) as client:
                for product_name, cat_url, weight, fiber, price in _CATEGORY_PAGES:
                    if len(results) >= limit:
                        break
                    try:
                        resp = await client.get(cat_url)
                    except Exception:
                        continue
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    variants = _parse_variants(soup)
                    if not variants:
                        continue

                    tasks = []
                    for v in variants:
                        if len(results) + len(tasks) >= limit:
                            break
                        color_name = v.get("name", "").strip()
                        if not color_name or not _is_solid(color_name):
                            continue
                        image_url = v.get("image")
                        if image_url:
                            image_url = _small_img(image_url)
                        product_url = v.get("url") or cat_url

                        tasks.append(self.make_yarn(
                            product_name=product_name,
                            color_name=color_name,
                            url=product_url,
                            image_url=image_url,
                            weight=weight,
                            fiber=fiber,
                            price=price,
                            extract_image_color=bool(image_url),
                        ))

                    for i in range(0, len(tasks), BATCH_SIZE):
                        batch = await asyncio.gather(*tasks[i : i + BATCH_SIZE])
                        results.extend(batch)

        except Exception:
            pass
        return results

    # ── Tier 2: color-name seed fallback ─────────────────────────────────────

    async def _fallback(self, limit: int) -> list[dict[str, Any]]:
        rows = _fallback_rows()
        tasks = [
            self.make_yarn(
                product_name=r[0], color_name=r[1],
                url=f"{self.base_url}/{r[0].lower().replace(' ', '-')}",
                weight=r[2], price=r[3], fiber=r[4],
            )
            for r in rows[:limit]
            if _is_solid(r[1])
        ]
        return list(await asyncio.gather(*tasks))
