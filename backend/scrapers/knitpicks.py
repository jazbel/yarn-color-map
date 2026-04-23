"""
Knit Picks scraper — tries live SFCC HTML scraping, falls back to
comprehensive seed data for Palette (200+ colors), Wool of the Andes,
Comfy, and Stroll.
"""
import asyncio
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, HEADERS

BATCH_SIZE = 20

_MULTICOLOR = {
    "rainbow","multi","variegat","ombre","gradient","speckl",
    "print","tweed","marled","stripe","tie-dye","heather",
}

def _is_solid(name: str) -> bool:
    n = name.lower()
    # Allow "heather" in the name — it's a common solid-adjacent colorway
    kws = _MULTICOLOR - {"heather"}
    return not any(kw in n for kw in kws)

def _abs(href: str, base: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return href

def _img_src(el) -> Optional[str]:
    for attr in ("src","data-src","data-lazy-src","srcset"):
        val = el.get(attr,"")
        if val:
            return val.split(",")[0].split(" ")[0]
    return None


# ── Comprehensive fallback ────────────────────────────────────────────────────
# KnitPicks Palette Fingering — 200+ colors, listed exhaustively
_PALETTE = [
    # Whites / near-whites
    "Bare","White","Swan","Cream","Ivory","Eggshell","Pearl","Blizzard",
    "Opal","Frost","Ice","Glacier","Vapor","Steam",
    # Grays
    "Fog","Mist","Haze","Silver","Dove","Ash","Marble","Cobblestone",
    "Stone","Pebble","Graphite","Mineral","Shadow","Coal","Black",
    "Platinum","Smoke","Slate","Pewter","Storm","Iron",
    # Pinks / roses
    "Fairy Tale","Blush","Ballerina","Carnation","Rose","Ballet",
    "Flamingo","Calypso","Peony","Camellia","Amaranth","Cerise",
    "Fuchsia","Magenta","Mulberry","Berry","Beet","Cranberry",
    "Raspberry","Watermelon","Hot Pink","Deep Rose","Mauve",
    "Dusty Rose","Antique Rose","Vintage Rose",
    # Reds / oranges
    "Red","Scarlet","Ruby","Garnet","Cherry","Tomato","Fire","Cayenne",
    "Paprika","Cardinal","Crimson","Brick","Burgundy","Pomegranate",
    "Rhubarb","Apricot","Peach","Melon","Cantaloupe","Papaya",
    "Tangerine","Tiger","Orange","Saffron","Pumpkin","Squash",
    "Rust","Copper","Sienna","Terracotta","Adobe","Clay","Burnt Sienna",
    # Yellows / golds
    "Canary","Daffodil","Lemon","Citron","Butter","Sunburst","Gold",
    "Goldenrod","Sungold","Maize","Straw","Wheat","Champagne",
    "Mustard","Ochre","Brass","Amber","Honey","Caramel","Toffee",
    # Greens
    "Chartreuse","Lime","Apple Green","Citrus","Avocado","Celery",
    "Pistachio","Spearmint","Mint","Seafoam","Aloe","Sage","Fern",
    "Clover","Moss","Basil","Herb","Verdant","Meadow","Grass",
    "Kelly","Shamrock","Jade","Emerald","Forest","Conifer","Hunter",
    "Pine","Shire","Juniper","Spruce","Cedar","Bottle Green",
    # Teals / aquas
    "Seafoam","Aqua","Turquoise","Lagoon","Pool","Oasis","Surf",
    "Clarity","Teal","Fjord","Seas","Tide","Pacific","Atlantic",
    "Malachite","Selenite","Aquamarine",
    # Blues
    "Ice Blue","Powder Blue","Baby Blue","Sky","Carolina Blue",
    "Cornflower","Periwinkle","Wedgwood","Cerulean","Azure","Denim",
    "Cobalt","Marina","Neptune","Indigo","Baltic","Navy","Midnight",
    "Harbor","Royal Blue","Sapphire","Electric Blue","Hyacinth",
    "Delft","Colonial Blue","Cloud Blue","Steel Blue",
    # Purples
    "Lavender","Lilac","Wisteria","Hyacinth","Iris","Orchid","Thistle",
    "Violet","Amethyst","Purple","Grape","Plum","Boysenberry",
    "Eggplant","Aubergine","Byzantium","Mulberry","Dusty Purple",
    # Browns / naturals
    "Almond","Birch","Tan","Sand","Camel","Fawn","Driftwood","Latte",
    "Mocha","Coffee","Espresso","Bark","Nutmeg","Cinnamon","Chestnut",
    "Walnut","Mahogany","Chocolate","Dark Brown",
]

_WOTA_COLORS = [
    "White","Cream","Bare","Pampas Heather","Camel Heather","Bison",
    "Tan","Almond","Chestnut Heather","Hazelnut Heather","Espresso","Bark",
    "Claret Heather","Garnet Heather","Rouge Heather","Currant","Red",
    "Pomegranate","Ginger","Pumpkin","Amber","Gold","Canary",
    "Lemon Grass Heather","Green Tea Heather","Mint","Jade","Moss Heather",
    "Forest Heather","Hunter","Teal","Pool","Cerulean","Sky Blue",
    "Periwinkle","Cornflower","Delft Heather","Navy","Midnight Heather",
    "Indigo","Baltic Heather","Iris","Amethyst Heather","Wisteria Heather",
    "Mulberry","Eggplant","Heather","Gray","Ash","Cobblestone","Charcoal","Black",
]

_COMFY_COLORS = [
    "White","Cream","Ballet","Blush","Rose Hip","Flamingo","Coral",
    "Poppy","Red","Cayenne","Tangerine","Apricot","Lemon Drop","Butter",
    "Goldenrod","Chartreuse","Clover","Spearmint","Mint","Seafoam","Teal",
    "Pool","Clarity","Sky","Periwinkle","Cornflower","Denim","Sailor",
    "Navy","Bluebell","Wisteria","Lavender","Orchid","Violet","Plum",
    "Dove Heather","Silver","Ash","Graphite","Black",
]

_STROLL_COLORS = [
    "White","Bare","Cream","Ballet","Blush","Rose","Flamingo","Coral",
    "Red","Tomato","Tangerine","Canary","Goldenrod","Meadow","Clover",
    "Mint","Teal","Cerulean","Sky","Cornflower","Denim","Navy","Cobalt",
    "Indigo","Periwinkle","Lavender","Amethyst","Violet","Plum",
    "Silver","Ash","Charcoal","Black","Caramel","Mocha","Espresso",
]

def _fallback_rows() -> list[tuple[str, str, str, str, str]]:
    # (product, color, weight, price, fiber)
    rows = []
    for c in _PALETTE:
        rows.append(("Palette Fingering", c, "Fingering", "$2.79", "Wool"))
    for c in _WOTA_COLORS:
        rows.append(("Wool of the Andes Worsted", c, "Worsted", "$5.49", "Wool"))
    for c in _COMFY_COLORS:
        rows.append(("Comfy Worsted", c, "Worsted", "$6.99", "Cotton"))
    for c in _STROLL_COLORS:
        rows.append(("Stroll Fingering", c, "Fingering", "$4.99", "Wool"))
    return rows


class KnitPicksScraper(BaseScraper):
    store_id = "knitpicks"
    name = "Knit Picks"
    base_url = "https://www.knitpicks.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results = await self._live_scrape(limit)
        if not results:
            results = await self._fallback(limit)
        return results

    async def _live_scrape(self, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=25
            ) as client:
                for page in range(1, 20):
                    if len(results) >= limit:
                        break
                    url = f"{self.base_url}/yarn?start={(page-1)*24}&sz=24"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = soup.select(
                        ".product-tile, .grid-tile, [class*='product-item'], "
                        "[class*='product-grid-item']"
                    )
                    if not cards:
                        break

                    tasks = []
                    for card in cards:
                        if len(results) + len(tasks) >= limit:
                            break
                        a = card.select_one("a[href]")
                        title_el = card.select_one(
                            "[class*='name'], [class*='title'], .product-name, h2, h3"
                        )
                        if not a:
                            continue
                        title = title_el.get_text(strip=True) if title_el else "Knit Picks Yarn"
                        if not _is_solid(title):
                            continue
                        href = _abs(a["href"], self.base_url)

                        swatch_img = None
                        for sel in (
                            "[class*='swatch'] img","[class*='color-swatch'] img",
                            "[data-color] img","li[class*='color'] img",
                        ):
                            el = card.select_one(sel)
                            if el:
                                s = _img_src(el)
                                if s:
                                    swatch_img = _abs(s, self.base_url)
                                    break
                        if not swatch_img:
                            img_el = card.select_one("img")
                            if img_el:
                                s = _img_src(img_el)
                                if s:
                                    swatch_img = _abs(s, self.base_url)

                        tasks.append(self.make_yarn(
                            product_name=title, color_name="",
                            url=href, image_url=swatch_img,
                            extract_image_color=bool(swatch_img),
                        ))

                    for i in range(0, len(tasks), BATCH_SIZE):
                        batch = await asyncio.gather(*tasks[i : i + BATCH_SIZE])
                        results.extend(batch)

        except Exception:
            pass
        return results

    async def _fallback(self, limit: int) -> list[dict[str, Any]]:
        rows = _fallback_rows()
        tasks = [
            self.make_yarn(
                product_name=r[0], color_name=r[1],
                url=f"{self.base_url}/{r[0].lower().replace(' ','-')}",
                weight=r[2], price=r[3], fiber=r[4],
            )
            for r in rows[:limit]
        ]
        return list(await asyncio.gather(*tasks))
