"""
Knitting for Olive scraper.

KFO uses Shopify at knittingforolive.com/collections/yarn.
Unlike most Shopify yarn stores, each color is its own product rather than a
variant. Title format: "Knitting for Olive <YarnName> - <ColorName>"
The product_type field encodes the base yarn (merino, heavymerino, etc.).
"""
import asyncio
import re
from typing import Any, Optional

import httpx

from scrapers.base import BaseScraper, HEADERS

PAGE_LIMIT = 250
BATCH_SIZE = 20

_MULTICOLOR = {
    "rainbow", "multi", "variegat", "ombre", "gradient", "speckl",
    "print", "tweed", "marled", "stripe", "tie-dye",
}

# product_type value → (weight, fiber)
_TYPE_META: dict[str, tuple[str, str]] = {
    "merino":           ("Fingering", "Wool"),
    "heavymerino":      ("DK",        "Wool"),
    "Soft Silk Mohair": ("Lace",      "Mohair"),
    "Pure Silk":        ("Sport",     "Silk"),
    "Cottonmerino7030": ("Sport",     "Cotton"),
    "Cashmere":         ("Sport",     "Cashmere"),
    "No Waste Wool":    ("DK",        "Wool"),
}

# Fallback keyword → product_type key (used when product_type is empty)
_NAME_KEYWORDS: list[tuple[str, str]] = [
    ("heavy merino",    "heavymerino"),
    ("soft silk mohair","Soft Silk Mohair"),
    ("pure silk",       "Pure Silk"),
    ("cottonmerino",    "Cottonmerino7030"),
    ("cotton merino",   "Cottonmerino7030"),
    ("cashmere",        "Cashmere"),
    ("no waste wool",   "No Waste Wool"),
    ("merino",          "merino"),
]


def _is_solid(name: str) -> bool:
    n = name.lower()
    return not any(kw in n for kw in _MULTICOLOR)


def _shopify_img(url: str, size: int = 300) -> str:
    m = re.match(r"^(.*?)(\.[a-zA-Z]+)(\?.*)?$", url)
    if m:
        return f"{m.group(1)}_{size}x{m.group(2)}{m.group(3) or ''}"
    return url


def _weight_fiber(product: dict) -> tuple[str, str]:
    pt = product.get("product_type", "")
    if pt in _TYPE_META:
        return _TYPE_META[pt]
    # Infer from the yarn-name portion of the title
    name_lower = product.get("title", "").lower().replace("knitting for olive", "")
    for keyword, type_key in _NAME_KEYWORDS:
        if keyword in name_lower:
            return _TYPE_META[type_key]
    return ("Fingering", "Wool")


class KnittingForOliveScraper(BaseScraper):
    store_id = "knittingforolive"
    name = "Knitting for Olive"
    base_url = "https://knittingforolive.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=30
            ) as client:
                while len(results) < limit:
                    resp = await client.get(
                        f"{self.base_url}/collections/yarn/products.json"
                        f"?limit={PAGE_LIMIT}&page={page}"
                    )
                    if resp.status_code != 200:
                        break
                    products = resp.json().get("products", [])
                    if not products:
                        break

                    tasks = []
                    for product in products:
                        if len(results) + len(tasks) >= limit:
                            break

                        title = product.get("title", "")
                        if " - " not in title:
                            continue

                        # "Knitting for Olive Soft Silk Mohair - Dusty Dove Blue"
                        product_name, color_name = title.rsplit(" - ", 1)
                        color_name = color_name.strip()
                        if not color_name or not _is_solid(color_name):
                            continue

                        weight, fiber = _weight_fiber(product)

                        variants = product.get("variants", [])
                        price_raw = variants[0].get("price") if variants else None
                        price = f"${float(price_raw):.2f}" if price_raw else None

                        images = product.get("images", [])
                        image_url = _shopify_img(images[0]["src"]) if images else None

                        handle = product.get("handle", "")
                        tasks.append(self.make_yarn(
                            product_name=product_name,
                            color_name=color_name,
                            url=f"{self.base_url}/products/{handle}",
                            image_url=image_url,
                            weight=weight,
                            fiber=fiber,
                            price=price,
                            extract_image_color=bool(image_url),
                        ))

                    for i in range(0, len(tasks), BATCH_SIZE):
                        batch = await asyncio.gather(*tasks[i : i + BATCH_SIZE])
                        results.extend(batch)

                    if len(products) < PAGE_LIMIT:
                        break
                    page += 1

        except Exception:
            pass
        return results
