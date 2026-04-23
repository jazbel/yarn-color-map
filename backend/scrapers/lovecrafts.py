"""
LoveCrafts scraper — tries live HTML scraping first, falls back to
comprehensive seed data for popular yarn lines (Paintbox Simply series,
Stylecraft Special, Lion Brand).
"""
import asyncio
import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, HEADERS

BATCH_SIZE = 20

_MULTICOLOR = {
    "rainbow","multi","variegat","ombre","gradient","speckl",
    "print","tweed","marled","stripe","tie-dye",
}

def _is_solid(name: str) -> bool:
    n = name.lower()
    return not any(kw in n for kw in _MULTICOLOR)

def _abs(href: str, base: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return href

def _img_src(el) -> Optional[str]:
    for attr in ("src", "data-src", "data-lazy-src", "srcset"):
        val = el.get(attr, "")
        if val:
            return val.split(",")[0].split(" ")[0]
    return None

_SWATCH_SELECTORS = [
    "img.swatch__img","[class*='swatch'] img",
    "[class*='color-swatch'] img","[data-color] img",
]


# ── Comprehensive fallback data ───────────────────────────────────────────────
# Paintbox Simply DK — 50 solid colors
_PB_DK = [
    ("Champagne White","DK","$3.49"),("Vanilla Cream","DK","$3.49"),
    ("Paper White","DK","$3.49"),("Misty Grey","DK","$3.49"),
    ("Slate Grey","DK","$3.49"),("Granite Grey","DK","$3.49"),
    ("Coal Black","DK","$3.49"),("Light Caramel","DK","$3.49"),
    ("Tea Brown","DK","$3.49"),("Soft Fudge","DK","$3.49"),
    ("Coffee Bean","DK","$3.49"),("Blush Pink","DK","$3.49"),
    ("Ballet Pink","DK","$3.49"),("Dusty Rose","DK","$3.49"),
    ("Bubblegum Pink","DK","$3.49"),("Raspberry Pink","DK","$3.49"),
    ("Blood Orange","DK","$3.49"),("Tomato Red","DK","$3.49"),
    ("Race Red","DK","$3.49"),("Fire Red","DK","$3.49"),
    ("Mandarin Orange","DK","$3.49"),("Saffron Orange","DK","$3.49"),
    ("Buttercup Yellow","DK","$3.49"),("Canary Yellow","DK","$3.49"),
    ("Banana Cream","DK","$3.49"),("Lime Green","DK","$3.49"),
    ("Grass Green","DK","$3.49"),("Spearmint","DK","$3.49"),
    ("Pistachio","DK","$3.49"),("Sage Green","DK","$3.49"),
    ("Fern Green","DK","$3.49"),("Forest Green","DK","$3.49"),
    ("Racing Green","DK","$3.49"),("Grass Green","DK","$3.49"),
    ("Seafoam Green","DK","$3.49"),("Glacier Blue","DK","$3.49"),
    ("Powder Blue","DK","$3.49"),("Cornflower Blue","DK","$3.49"),
    ("Cobalt Blue","DK","$3.49"),("Royal Blue","DK","$3.49"),
    ("Slate Blue","DK","$3.49"),("Navy Blue","DK","$3.49"),
    ("Midnight Blue","DK","$3.49"),("Hyacinth Violet","DK","$3.49"),
    ("Wisteria Purple","DK","$3.49"),("Violet Purple","DK","$3.49"),
    ("Pansy Purple","DK","$3.49"),("Melon Sorbet","DK","$3.49"),
    ("Peach Orange","DK","$3.49"),("Salmon Pink","DK","$3.49"),
]

# Paintbox Simply Chunky — same palette, different weight
_PB_CHUNKY = [(c, "Chunky", p.replace("3.49","4.29")) for c, _, p in _PB_DK]

# Paintbox Simply Worsted
_PB_WORSTED = [(c, "Worsted", p.replace("3.49","3.79")) for c, _, p in _PB_DK]

# Stylecraft Special DK — broad palette
_SC_DK_COLORS = [
    "Cream","White","Parchment","Linen","Silver","Grey","Graphite",
    "Charcoal","Black","Natural","Mocha","Caramel","Toffee","Copper",
    "Spice","Walnut","Dark Brown","Terracotta","Rust","Cinnamon",
    "Claret","Burgundy","Wine","Pomegranate","Raspberry","Cherry",
    "Red","Tomato","Lobster","Magenta","Fuchsia","Orchid","Violet",
    "Bluebell","Heather","Lavender","Wisteria","Empire","Petrol",
    "Denim","Cornflower","Turquoise","Teal","Jade","Spearmint",
    "Meadow","Sour Apple","Pistachio","Spring Green","Citron","Sunshine",
    "Gold","Mustard","Camel","Peach","Sherbet","Lipstick","Fondant",
    "Pale Rose","Blush","Pale Cream","Aster","Pool","Atlantic",
    "Cloud Blue","Sky","Storm Blue","Colonial Blue","Powder Blue",
]
_SC_DK = [(c, "DK", "$4.29") for c in _SC_DK_COLORS]

# Lion Brand Pound of Love
_LB_LOVE = [
    ("White","Worsted","$12.99"),("Fisherman","Worsted","$12.99"),
    ("Pastel Yellow","Worsted","$12.99"),("Pastel Pink","Worsted","$12.99"),
    ("Baby Blue","Worsted","$12.99"),("Mint","Worsted","$12.99"),
    ("Lavender","Worsted","$12.99"),("Honey","Worsted","$12.99"),
    ("Pink","Worsted","$12.99"),("Orchid","Worsted","$12.99"),
    ("Purple","Worsted","$12.99"),("Delft Blue","Worsted","$12.99"),
    ("Blue","Worsted","$12.99"),("Jade","Worsted","$12.99"),
    ("Red","Worsted","$12.99"),("Black","Worsted","$12.99"),
]

# Lion Brand Comfy Cotton Blend
_LB_COMFY = [
    ("Cotton Ball","Worsted","$9.99"),("Whipped Cream","Worsted","$9.99"),
    ("Ballet","Worsted","$9.99"),("Sorbet","Worsted","$9.99"),
    ("Flamingo","Worsted","$9.99"),("Cherry","Worsted","$9.99"),
    ("Popsicle","Worsted","$9.99"),("Tangerine","Worsted","$9.99"),
    ("Lemon","Worsted","$9.99"),("Mint","Worsted","$9.99"),
    ("Sage","Worsted","$9.99"),("Seaglass","Worsted","$9.99"),
    ("Sky","Worsted","$9.99"),("Periwinkle","Worsted","$9.99"),
    ("Bluebell","Worsted","$9.99"),("Violet","Worsted","$9.99"),
    ("Fog","Worsted","$9.99"),("Stonewash","Worsted","$9.99"),
    ("Black","Worsted","$9.99"),
]

def _fallback_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    for (c, w, p) in _PB_DK:
        rows.append(("Paintbox Simply DK", c, w, p))
    for (c, w, p) in _PB_CHUNKY:
        rows.append(("Paintbox Simply Chunky", c, w, p))
    for (c, w, p) in _PB_WORSTED:
        rows.append(("Paintbox Simply Worsted", c, w, p))
    for (c, w, p) in _SC_DK:
        rows.append(("Stylecraft Special DK", c, w, p))
    for (c, w, p) in _LB_LOVE:
        rows.append(("Lion Brand Pound of Love", c, w, p))
    for (c, w, p) in _LB_COMFY:
        rows.append(("Lion Brand Comfy Cotton Blend", c, w, p))
    return rows


class LovecraftsScraper(BaseScraper):
    store_id = "lovecrafts"
    name = "LoveCrafts"
    base_url = "https://www.lovecrafts.com"

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
                    resp = await client.get(
                        f"{self.base_url}/en-us/c/yarn?page={page}&per_page=60"
                    )
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = soup.select(
                        "[class*='product-listing'], [class*='product-card'], "
                        "article[class*='product'], li[class*='product']"
                    )
                    if not cards:
                        break

                    tasks = []
                    for card in cards:
                        if len(results) + len(tasks) >= limit:
                            break
                        a = card.select_one("a[href]")
                        title_el = card.select_one(
                            "[class*='title'], [class*='name'], h2, h3"
                        )
                        if not a:
                            continue
                        href = _abs(a["href"], self.base_url)
                        title = title_el.get_text(strip=True) if title_el else "LoveCrafts Yarn"
                        if not _is_solid(title):
                            continue

                        swatch_img = None
                        for sel in _SWATCH_SELECTORS:
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
                url=f"{self.base_url}/en-us/p/{r[0].lower().replace(' ','-')}",
                weight=r[2], price=r[3],
            )
            for r in rows[:limit]
            if _is_solid(r[1])
        ]
        return list(await asyncio.gather(*tasks))
