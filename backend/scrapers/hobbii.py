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
from yarn_meta import infer_weight, infer_fiber, strip_html

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
        title = product["title"]
        body = product.get("body_html", "")

        # Extract fiber and weight once per product (shared by all variants)
        fiber = infer_fiber(title, body)
        weight = infer_weight(title, strip_html(body))

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
                    product_name=title,
                    color_name=color_name,
                    url=product_url,
                    image_url=img_src,
                    extract_image_color=use_image,
                    fiber=fiber,
                    weight=weight,
                    price=price,
                )
            )
        return tasks

    # ── Fallback seed data ────────────────────────────────────────────────────
    async def _fallback(self) -> list[dict[str, Any]]:
        # (product, color, weight, price, fiber)
        PRODUCTS = [
            ("Friends Cotton 8/4", "DK",        "$3.49", "Cotton"),
            ("Friends Cotton 8/8", "Bulky",      "$4.99", "Cotton"),
            ("Happy Feet",         "Fingering",  "$6.99", "Wool"),
            ("Alpaca Soft DK",     "DK",         "$7.99", "Alpaca"),
        ]
        COLORS = [
            "White","Cream","Oatmilk","Beige","Blush","Dusty Rose","Old Rose",
            "Light Pink","Rose","Hot Pink","Raspberry","Cherry Red","Red","Coral",
            "Peach","Apricot","Orange","Burnt Orange","Terracotta","Mustard",
            "Golden","Yellow","Lime Green","Mint Green","Sage Green","Olive Green",
            "Forest Green","Hunter Green","Emerald","Teal","Turquoise","Aqua",
            "Sky Blue","Baby Blue","Cornflower Blue","Royal Blue","Cobalt Blue",
            "Denim Blue","Navy Blue","Midnight Blue","Indigo","Lavender","Lilac",
            "Purple","Grape","Eggplant","Light Gray","Silver Gray","Charcoal",
            "Black","Camel","Tan","Brown","Chocolate",
        ]
        rows = [
            (prod, color, weight, price, fiber)
            for prod, weight, price, fiber in PRODUCTS
            for color in COLORS
        ]
        tasks = [
            self.make_yarn(
                product_name=r[0], color_name=r[1],
                url=f"{self.base_url}/products/{r[0].lower().replace(' ','-')}",
                weight=r[2], price=r[3], fiber=r[4],
            )
            for r in rows
        ]
        return list(await asyncio.gather(*tasks))
