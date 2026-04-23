"""
Hobbii scraper — uses the Shopify /collections/yarn/products.json endpoint.
Each variant has a featured_image.src that is per-color, so color extraction
is accurate.  Images are downloaded in batches of BATCH_SIZE to avoid
hammering the CDN.
"""
import asyncio
import re
from typing import Any, Optional

import httpx

from scrapers.base import BaseScraper, HEADERS

# Shopify max items per page
PAGE_LIMIT = 250
# Max concurrent image downloads per batch
BATCH_SIZE = 20

# Words in a variant title that indicate a non-solid (skip these)
_MULTICOLOR = {
    "rainbow", "multi", "variegat", "ombre", "gradient", "speckl",
    "print", "tweed", "marled", "stripe", "tie-dye", "mix bag",
    "kit (", "kit[", "neon rainbow", "pastel rainbow",
}

def _is_solid(title: str) -> bool:
    t = title.lower()
    return not any(kw in t for kw in _MULTICOLOR)


def _shopify_img(url: str, size: int = 300) -> str:
    m = re.match(r"^(.*?)(\.[a-zA-Z]+)(\?.*)?$", url)
    if m:
        return f"{m.group(1)}_{size}x{m.group(2)}{m.group(3) or ''}"
    return url


def _variant_color_name(variant: dict, product: dict) -> str:
    options = product.get("options", [])
    for i, opt in enumerate(options):
        if opt.get("name", "").lower() in ("color", "colour", "farbe", "couleur"):
            val = variant.get(f"option{i + 1}", "")
            if val and val.lower() != "default title":
                return val
    title = variant.get("title", "")
    return "" if title.lower() == "default title" else title


class HobbiiScraper(BaseScraper):
    store_id = "hobbii"
    name = "Hobbii"
    base_url = "https://hobbii.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results = await self._live_scrape(limit)
        if not results:
            results = await self._fallback()
        return results

    # ── Shopify JSON API ──────────────────────────────────────────────────────
    async def _live_scrape(self, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=30
            ) as client:
                while len(results) < limit:
                    url = (
                        f"{self.base_url}/collections/yarn/products.json"
                        f"?limit={PAGE_LIMIT}&page={page}"
                    )
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break
                    products = resp.json().get("products", [])
                    if not products:
                        break

                    # Build all tasks for this page
                    tasks: list = []
                    for product in products:
                        remaining = limit - len(results) - len(tasks)
                        if remaining <= 0:
                            break
                        tasks += self._product_tasks(product, remaining)

                    # Process in batches so we don't open hundreds of
                    # simultaneous image connections
                    for i in range(0, len(tasks), BATCH_SIZE):
                        batch = await asyncio.gather(*tasks[i : i + BATCH_SIZE])
                        results.extend(batch)

                    if len(products) < PAGE_LIMIT:
                        break
                    page += 1

        except Exception:
            pass
        return results

    def _product_tasks(self, product: dict, remaining: int) -> list:
        img_map: dict[int, str] = {
            img["id"]: img["src"]
            for img in product.get("images", [])
        }
        first_img: Optional[str] = (
            product["images"][0]["src"] if product.get("images") else None
        )
        handle = product.get("handle", "")
        product_url = f"{self.base_url}/products/{handle}"

        tasks = []
        for variant in product.get("variants", []):
            if len(tasks) >= remaining:
                break

            color_name = _variant_color_name(variant, product)
            if not _is_solid(color_name):
                continue

            fi = variant.get("featured_image")
            if fi and fi.get("src"):
                img_src: Optional[str] = _shopify_img(fi["src"])
                use_image = True
            elif variant.get("image_id") and variant["image_id"] in img_map:
                img_src = _shopify_img(img_map[variant["image_id"]])
                use_image = True
            else:
                img_src = first_img
                use_image = False

            price_raw = variant.get("price")
            price = f"${float(price_raw):.2f}" if price_raw else None

            tasks.append(
                self.make_yarn(
                    product_name=product["title"],
                    color_name=color_name,
                    url=product_url,
                    image_url=img_src,
                    extract_image_color=use_image,
                    price=price,
                )
            )
        return tasks

    # ── Fallback seed data ────────────────────────────────────────────────────
    async def _fallback(self) -> list[dict[str, Any]]:
        rows = [
            # Friends Cotton 8/4 — ~50 solid colors
            ("Friends Cotton 8/4","White",         "DK","$3.49"),
            ("Friends Cotton 8/4","Oatmilk",       "DK","$3.49"),
            ("Friends Cotton 8/4","Cream",          "DK","$3.49"),
            ("Friends Cotton 8/4","Beige",          "DK","$3.49"),
            ("Friends Cotton 8/4","Blush",          "DK","$3.49"),
            ("Friends Cotton 8/4","Dusty Rose",     "DK","$3.49"),
            ("Friends Cotton 8/4","Old Rose",       "DK","$3.49"),
            ("Friends Cotton 8/4","Light Pink",     "DK","$3.49"),
            ("Friends Cotton 8/4","Rose",           "DK","$3.49"),
            ("Friends Cotton 8/4","Hot Pink",       "DK","$3.49"),
            ("Friends Cotton 8/4","Raspberry",      "DK","$3.49"),
            ("Friends Cotton 8/4","Cherry Red",     "DK","$3.49"),
            ("Friends Cotton 8/4","Red",            "DK","$3.49"),
            ("Friends Cotton 8/4","Coral",          "DK","$3.49"),
            ("Friends Cotton 8/4","Peach",          "DK","$3.49"),
            ("Friends Cotton 8/4","Apricot",        "DK","$3.49"),
            ("Friends Cotton 8/4","Orange",         "DK","$3.49"),
            ("Friends Cotton 8/4","Burnt Orange",   "DK","$3.49"),
            ("Friends Cotton 8/4","Terracotta",     "DK","$3.49"),
            ("Friends Cotton 8/4","Mustard",        "DK","$3.49"),
            ("Friends Cotton 8/4","Golden",         "DK","$3.49"),
            ("Friends Cotton 8/4","Yellow",         "DK","$3.49"),
            ("Friends Cotton 8/4","Lime Green",     "DK","$3.49"),
            ("Friends Cotton 8/4","Mint Green",     "DK","$3.49"),
            ("Friends Cotton 8/4","Sage Green",     "DK","$3.49"),
            ("Friends Cotton 8/4","Olive Green",    "DK","$3.49"),
            ("Friends Cotton 8/4","Forest Green",   "DK","$3.49"),
            ("Friends Cotton 8/4","Hunter Green",   "DK","$3.49"),
            ("Friends Cotton 8/4","Emerald",        "DK","$3.49"),
            ("Friends Cotton 8/4","Teal",           "DK","$3.49"),
            ("Friends Cotton 8/4","Turquoise",      "DK","$3.49"),
            ("Friends Cotton 8/4","Aqua",           "DK","$3.49"),
            ("Friends Cotton 8/4","Sky Blue",       "DK","$3.49"),
            ("Friends Cotton 8/4","Baby Blue",      "DK","$3.49"),
            ("Friends Cotton 8/4","Cornflower Blue","DK","$3.49"),
            ("Friends Cotton 8/4","Royal Blue",     "DK","$3.49"),
            ("Friends Cotton 8/4","Cobalt Blue",    "DK","$3.49"),
            ("Friends Cotton 8/4","Denim Blue",     "DK","$3.49"),
            ("Friends Cotton 8/4","Navy Blue",      "DK","$3.49"),
            ("Friends Cotton 8/4","Midnight Blue",  "DK","$3.49"),
            ("Friends Cotton 8/4","Indigo",         "DK","$3.49"),
            ("Friends Cotton 8/4","Lavender",       "DK","$3.49"),
            ("Friends Cotton 8/4","Lilac",          "DK","$3.49"),
            ("Friends Cotton 8/4","Purple",         "DK","$3.49"),
            ("Friends Cotton 8/4","Grape",          "DK","$3.49"),
            ("Friends Cotton 8/4","Eggplant",       "DK","$3.49"),
            ("Friends Cotton 8/4","Heather",        "DK","$3.49"),
            ("Friends Cotton 8/4","Light Gray",     "DK","$3.49"),
            ("Friends Cotton 8/4","Silver Gray",    "DK","$3.49"),
            ("Friends Cotton 8/4","Charcoal",       "DK","$3.49"),
            ("Friends Cotton 8/4","Black",          "DK","$3.49"),
            ("Friends Cotton 8/4","Camel",          "DK","$3.49"),
            ("Friends Cotton 8/4","Tan",            "DK","$3.49"),
            ("Friends Cotton 8/4","Brown",          "DK","$3.49"),
            ("Friends Cotton 8/4","Chocolate",      "DK","$3.49"),
            # Friends Cotton 8/8 (bulky)
            ("Friends Cotton 8/8","White",          "Bulky","$4.99"),
            ("Friends Cotton 8/8","Cream",          "Bulky","$4.99"),
            ("Friends Cotton 8/8","Blush",          "Bulky","$4.99"),
            ("Friends Cotton 8/8","Rose",           "Bulky","$4.99"),
            ("Friends Cotton 8/8","Raspberry",      "Bulky","$4.99"),
            ("Friends Cotton 8/8","Red",            "Bulky","$4.99"),
            ("Friends Cotton 8/8","Orange",         "Bulky","$4.99"),
            ("Friends Cotton 8/8","Mustard",        "Bulky","$4.99"),
            ("Friends Cotton 8/8","Yellow",         "Bulky","$4.99"),
            ("Friends Cotton 8/8","Lime Green",     "Bulky","$4.99"),
            ("Friends Cotton 8/8","Forest Green",   "Bulky","$4.99"),
            ("Friends Cotton 8/8","Teal",           "Bulky","$4.99"),
            ("Friends Cotton 8/8","Sky Blue",       "Bulky","$4.99"),
            ("Friends Cotton 8/8","Royal Blue",     "Bulky","$4.99"),
            ("Friends Cotton 8/8","Navy Blue",      "Bulky","$4.99"),
            ("Friends Cotton 8/8","Purple",         "Bulky","$4.99"),
            ("Friends Cotton 8/8","Lavender",       "Bulky","$4.99"),
            ("Friends Cotton 8/8","Charcoal",       "Bulky","$4.99"),
            ("Friends Cotton 8/8","Black",          "Bulky","$4.99"),
            # Happy Feet sock yarn
            ("Happy Feet","Ivory",           "Fingering","$6.99"),
            ("Happy Feet","Blush",           "Fingering","$6.99"),
            ("Happy Feet","Coral",           "Fingering","$6.99"),
            ("Happy Feet","Red",             "Fingering","$6.99"),
            ("Happy Feet","Tangerine",       "Fingering","$6.99"),
            ("Happy Feet","Mustard",         "Fingering","$6.99"),
            ("Happy Feet","Yellow",          "Fingering","$6.99"),
            ("Happy Feet","Sage Green",      "Fingering","$6.99"),
            ("Happy Feet","Forest Green",    "Fingering","$6.99"),
            ("Happy Feet","Teal",            "Fingering","$6.99"),
            ("Happy Feet","Cerulean",        "Fingering","$6.99"),
            ("Happy Feet","Navy Blue",       "Fingering","$6.99"),
            ("Happy Feet","Indigo",          "Fingering","$6.99"),
            ("Happy Feet","Lavender",        "Fingering","$6.99"),
            ("Happy Feet","Gray",            "Fingering","$6.99"),
            ("Happy Feet","Black",           "Fingering","$6.99"),
            # Alpaca Soft DK
            ("Alpaca Soft DK","Simply White", "DK","$7.99"),
            ("Alpaca Soft DK","Cream",        "DK","$7.99"),
            ("Alpaca Soft DK","Blush",        "DK","$7.99"),
            ("Alpaca Soft DK","Dusty Rose",   "DK","$7.99"),
            ("Alpaca Soft DK","Rose",         "DK","$7.99"),
            ("Alpaca Soft DK","Red",          "DK","$7.99"),
            ("Alpaca Soft DK","Coral",        "DK","$7.99"),
            ("Alpaca Soft DK","Peach",        "DK","$7.99"),
            ("Alpaca Soft DK","Mustard",      "DK","$7.99"),
            ("Alpaca Soft DK","Golden",       "DK","$7.99"),
            ("Alpaca Soft DK","Sage Green",   "DK","$7.99"),
            ("Alpaca Soft DK","Forest Green", "DK","$7.99"),
            ("Alpaca Soft DK","Teal",         "DK","$7.99"),
            ("Alpaca Soft DK","Sky Blue",     "DK","$7.99"),
            ("Alpaca Soft DK","Royal Blue",   "DK","$7.99"),
            ("Alpaca Soft DK","Navy Blue",    "DK","$7.99"),
            ("Alpaca Soft DK","Lavender",     "DK","$7.99"),
            ("Alpaca Soft DK","Purple",       "DK","$7.99"),
            ("Alpaca Soft DK","Light Gray",   "DK","$7.99"),
            ("Alpaca Soft DK","Charcoal",     "DK","$7.99"),
            ("Alpaca Soft DK","Black",        "DK","$7.99"),
        ]
        tasks = [
            self.make_yarn(
                product_name=r[0], color_name=r[1],
                url=f"{self.base_url}/products/{r[0].lower().replace(' ','-')}",
                weight=r[2], price=r[3],
            )
            for r in rows
        ]
        return list(await asyncio.gather(*tasks))
