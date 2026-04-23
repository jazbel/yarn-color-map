"""
Michaels scraper.

Uses the GRS product search API found in robots.txt:
  POST /api/search/v1/grsapi/search/michaels/products/rankedProduct
  {"categoryCodePath":"root//Categories//809187838//809187839","start":N,"sz":40}

The search API returns 4 color variants per product. For products with more
colors we fetch the product detail page and parse variantSwatchUrls from the
embedded RSC payload.
"""
import asyncio
import json
import re
from typing import Any, Optional

import httpx

from scrapers.base import BaseScraper, HEADERS
from yarn_meta import infer_weight, infer_fiber

BATCH_SIZE = 20
PAGE_SIZE = 40

_API_URL = "https://www.michaels.com/api/search/v1/grsapi/search/michaels/products/rankedProduct"
_CATEGORY = "root//Categories//809187838//809187839"

_API_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

_MULTICOLOR = {
    "rainbow", "multi", "variegat", "ombre", "gradient", "speckl",
    "print", "tweed", "marled", "stripe", "tie-dye", "heather",
    "splash", "fleck", "twinkle", "sparkle", "confetti", "denim",
    "ombre", "floral",
}


def _is_solid(name: str) -> bool:
    n = name.lower()
    return not any(kw in n for kw in _MULTICOLOR)


def _resize_img(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return re.sub(r'\|\d+:\d+', '|300:300', url)


def _slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _parse_price(item: dict) -> Optional[str]:
    raw = item.get('itemPrice') or '{}'
    try:
        ip = json.loads(raw) if isinstance(raw, str) else raw
        return ip.get('price') or None
    except Exception:
        return None


def _parse_swatch_urls(html: str) -> dict[str, str]:
    """Extract {colorName: swatchImageUrl} from product detail page RSC payload."""
    idx = html.find('variantSwatchUrls')
    if idx < 0:
        return {}
    chunk = html[idx:]
    start = chunk.find('{')
    if start < 0:
        return {}
    depth = 0
    for i, c in enumerate(chunk[start:]):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                raw = chunk[start:start + i + 1]
                cleaned = raw.replace('\\"', '"')
                try:
                    return json.loads(cleaned)
                except Exception:
                    return {}
    return {}


class MichaelsScraper(BaseScraper):
    store_id = "michaels"
    name = "Michaels"
    base_url = "https://www.michaels.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen: set = set()

        try:
            async with httpx.AsyncClient(
                headers=_API_HEADERS,
                follow_redirects=True,
                timeout=30,
            ) as client:
                start_offset = 0
                while len(results) < limit:
                    resp = await client.post(
                        _API_URL,
                        json={
                            "categoryCodePath": _CATEGORY,
                            "start": start_offset,
                            "sz": PAGE_SIZE,
                        },
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    items = data.get("searchResults", {}).get("items", [])
                    if not items:
                        break

                    # Partition into simple (≤4 colors from API) vs. needs detail page
                    simple: list[tuple] = []
                    needs_detail: list[tuple] = []

                    for item in items:
                        product_name = item.get("productName", "")
                        master_sku = item.get("masterSku", "")
                        if not product_name or not master_sku:
                            continue

                        price = _parse_price(item)
                        weight = infer_weight(product_name)
                        fiber = infer_fiber(product_name)
                        url = f"{self.base_url}/product/{_slug(product_name)}-{master_sku}"

                        vm_raw = item.get("variantCountMap", "{}")
                        vm = json.loads(vm_raw) if isinstance(vm_raw, str) else vm_raw or {}
                        total_colors = vm.get("Color", 0)

                        subs_raw = item.get("subSkusWithColor", "[]")
                        subs = json.loads(subs_raw) if isinstance(subs_raw, str) else subs_raw or []

                        if total_colors > len(subs) and total_colors > 0:
                            needs_detail.append((url, product_name, price, weight, fiber))
                        else:
                            simple.append((product_name, url, price, weight, fiber, subs))

                    # ── Process simple items (use fullSizeUrl from search API) ──────
                    yarn_tasks = []
                    for product_name, url, price, weight, fiber, subs in simple:
                        for variant in subs:
                            if len(results) + len(yarn_tasks) >= limit:
                                break
                            color_name = variant.get("colorName", "").strip()
                            if not color_name or not _is_solid(color_name):
                                continue
                            key = f"{url}|{color_name}"
                            if key in seen:
                                continue
                            seen.add(key)
                            img = _resize_img(
                                variant.get("fullSizeUrl") or variant.get("swatchImageUrl")
                            )
                            yarn_tasks.append(self.make_yarn(
                                product_name=product_name,
                                color_name=color_name,
                                url=url,
                                image_url=img,
                                weight=weight,
                                fiber=fiber,
                                price=price,
                                extract_image_color=bool(img),
                            ))

                    for i in range(0, len(yarn_tasks), BATCH_SIZE):
                        batch = await asyncio.gather(*yarn_tasks[i:i + BATCH_SIZE])
                        results.extend(batch)
                    yarn_tasks.clear()

                    # ── Fetch product detail pages to get full color lists ─────────
                    for i in range(0, len(needs_detail), BATCH_SIZE):
                        if len(results) >= limit:
                            break
                        detail_batch = needs_detail[i:i + BATCH_SIZE]
                        page_resps = await asyncio.gather(*[
                            client.get(url) for url, *_ in detail_batch
                        ], return_exceptions=True)

                        yarn_tasks = []
                        for (url, product_name, price, weight, fiber), resp in zip(
                            detail_batch, page_resps
                        ):
                            if isinstance(resp, Exception):
                                continue
                            if resp.status_code != 200:
                                continue
                            swatches = _parse_swatch_urls(resp.text)
                            if not swatches:
                                continue
                            for color_name, swatch_url in swatches.items():
                                if len(results) + len(yarn_tasks) >= limit:
                                    break
                                if not color_name or not _is_solid(color_name):
                                    continue
                                key = f"{url}|{color_name}"
                                if key in seen:
                                    continue
                                seen.add(key)
                                img = _resize_img(swatch_url)
                                yarn_tasks.append(self.make_yarn(
                                    product_name=product_name,
                                    color_name=color_name,
                                    url=url,
                                    image_url=img,
                                    weight=weight,
                                    fiber=fiber,
                                    price=price,
                                    extract_image_color=bool(img),
                                ))

                        for j in range(0, len(yarn_tasks), BATCH_SIZE):
                            batch = await asyncio.gather(*yarn_tasks[j:j + BATCH_SIZE])
                            results.extend(batch)

                    start_offset += PAGE_SIZE

        except Exception:
            pass

        return results[:limit]
