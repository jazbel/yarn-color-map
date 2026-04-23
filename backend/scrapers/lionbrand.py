"""
Lion Brand scraper — uses their public Shopify storefront JSON API.

Lion Brand runs a Shopify store at lionbrand.com that exposes
/collections/all/products.json with per-variant featured_image data.
Each color variant maps to its own product photo; PIL extracts the
dominant hex from that image.

LoveCrafts (the original third store) blocks all server-side requests
with AWS WAF, so Lion Brand is used instead.
"""
import asyncio
import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, HEADERS
from yarn_meta import infer_weight, infer_fiber, strip_html

BATCH_SIZE = 20
PRODUCTS_PER_PAGE = 250

_MULTICOLOR = {
    "rainbow", "multi", "variegat", "ombre", "gradient", "speckl",
    "print", "tweed", "marled", "stripe", "tie-dye", "print",
    "fair isle", "jacquard",
}

# Keyword that indicates a product is yarn (not needles, books, patterns, etc.)
_YARN_KEYWORDS = {
    "yarn", "wool", "cotton", "acrylic", "blend", "mohair",
    "alpaca", "bamboo", "linen", "nylon", "silk", "chenille",
    "bulky", "worsted", "fingering", "dk", "sport", "lace",
}

def _is_solid(name: str) -> bool:
    n = name.lower()
    return not any(kw in n for kw in _MULTICOLOR)

_SIZE_RE = re.compile(
    r'^\s*(?:\d+\s*(?:oz|g|lb|m|yds?|yards?|skeins?|balls?)\.?'
    r'|(?:XS|S|M|L|XL|XXL|\d+(?:\.\d+)?))\s*$',
    re.I,
)

def _is_yarn_product(title: str) -> bool:
    """Require 'Yarn' in the product title — Lion Brand puts it there for all yarn SKUs."""
    return "yarn" in title.lower()

def _is_color_variant(title: str) -> bool:
    """Reject size/quantity variants that aren't color names."""
    return not _SIZE_RE.match(title)


class LionBrandScraper(BaseScraper):
    store_id = "lionbrand"
    name = "Lion Brand"
    base_url = "https://www.lionbrand.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results = await self._shopify_scrape(limit)
        return results

    async def _shopify_scrape(self, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen_ids: set = set()
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=30
            ) as client:
                for page in range(1, 40):
                    if len(results) >= limit:
                        break
                    resp = await client.get(
                        f"{self.base_url}/collections/all/products.json"
                        f"?limit={PRODUCTS_PER_PAGE}&page={page}"
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
                        body_html = product.get("body_html", "")
                        if not _is_yarn_product(title):
                            continue

                        images = product.get("images", [])
                        img_by_id: dict[int, str] = {
                            img["id"]: img["src"]
                            for img in images
                            if img.get("id") and img.get("src")
                        }
                        product_url = f"{self.base_url}/products/{product.get('handle','')}"

                        weight = infer_weight(title, strip_html(body_html))
                        fiber = infer_fiber(title, strip_html(body_html))

                        # Extract price from first variant
                        variants = product.get("variants", [])
                        price_raw = variants[0].get("price", "") if variants else ""
                        price = f"${price_raw}" if price_raw else None

                        for variant in variants:
                            if len(results) + len(tasks) >= limit:
                                break
                            color_name = variant.get("title", "").strip()
                            if not color_name or color_name == "Default Title":
                                continue
                            if not _is_solid(color_name) or not _is_color_variant(color_name):
                                continue

                            variant_id = variant.get("id")
                            if variant_id in seen_ids:
                                continue
                            seen_ids.add(variant_id)

                            # Get per-variant image (featured_image takes priority)
                            image_url: Optional[str] = None
                            feat = variant.get("featured_image")
                            if isinstance(feat, dict) and feat.get("src"):
                                image_url = feat["src"]
                            else:
                                img_id = variant.get("image_id")
                                if img_id and img_id in img_by_id:
                                    image_url = img_by_id[img_id]
                                elif images:
                                    image_url = images[0]["src"]

                            # Resize Shopify CDN images for speed
                            if image_url and "cdn.shopify.com" in image_url:
                                image_url = re.sub(
                                    r'(_\d+x\d*\.|_\d*x\d+\.)',
                                    '.',
                                    image_url
                                )
                                base, ext = image_url.rsplit(".", 1)
                                if "?" in ext:
                                    ext_clean, qs = ext.split("?", 1)
                                    image_url = f"{base}_300x.{ext_clean}?{qs}"
                                else:
                                    image_url = f"{base}_300x.{ext}"

                            tasks.append(self.make_yarn(
                                product_name=title,
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
