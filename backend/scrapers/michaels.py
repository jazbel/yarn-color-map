"""
Michaels scraper.

Uses the GRS product search API found in robots.txt:
  POST /api/search/v1/grsapi/search/michaels/products/rankedProduct

The API is capped at 15 results per query regardless of start/sz parameters.
To maximise coverage, we query across brand × yarnWeight facet combinations
which each return a different set of 15 ranked products.  Products are
deduplicated by masterSku, then their detail pages are fetched to get the
full variantSwatchUrls map (all color → swatch image pairs).
"""
import asyncio
import json
import re
from typing import Any, Optional

import httpx

from scrapers.base import BaseScraper, HEADERS
from yarn_meta import infer_weight, infer_fiber

BATCH_SIZE = 20

_API_URL = "https://www.michaels.com/api/search/v1/grsapi/search/michaels/products/rankedProduct"
_CATEGORY = "root//Categories//809187838//809187839"

_API_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# CYC weight numbers as returned by the Michaels facet API
_WEIGHT_FACETS = [
    "4 - Medium", "5 - Bulky", "3 - Light",
    "6 - Super Bulky", "1 - Super Fine", "2 - Fine", "7 - Jumbo",
]

# Major yarn brands available on Michaels
_BRAND_FACETS = [
    "Bernat", "Caron", "Lion Brand", "Loops and Threads",
    "Red Heart", "Patons", "Premier Yarns", "Universal Yarn",
    "Lion Brand Yarn", "Paintbox Yarns", "DMC", "HiKoo",
    "Wool and the Gang",
]

_MULTICOLOR = {
    "rainbow", "multi", "variegat", "ombre", "gradient", "speckl",
    "print", "tweed", "marled", "stripe", "tie-dye", "heather",
    "splash", "fleck", "twinkle", "sparkle", "confetti", "floral",
    "ombre", "denim",
}

# Map CYC number codes to canonical weight names
_CYCC_WEIGHT = {
    "1": "Fingering", "2": "Sport", "3": "DK",
    "4": "Worsted", "5": "Bulky", "6": "Super Bulky", "7": "Jumbo",
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


def _parse_weight_from_facet(facet_value: str) -> Optional[str]:
    """Map '4 - Medium' → 'Worsted'."""
    m = re.match(r'^(\d+)', facet_value.strip())
    if m:
        return _CYCC_WEIGHT.get(m.group(1))
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


async def _query_products(
    client: httpx.AsyncClient,
    facet_filters: list[dict],
) -> list[dict]:
    try:
        resp = await client.post(
            _API_URL,
            json={
                "categoryCodePath": _CATEGORY,
                "start": 0,
                "sz": 40,
                "facetFilters": facet_filters,
            },
        )
        if resp.status_code == 200:
            return resp.json().get("searchResults", {}).get("items", [])
    except Exception:
        pass
    return []


class MichaelsScraper(BaseScraper):
    store_id = "michaels"
    name = "Michaels"
    base_url = "https://www.michaels.com"

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen_products: set[str] = set()   # masterSku
        seen_colors: set[str] = set()     # url|colorName

        try:
            async with httpx.AsyncClient(
                headers=_API_HEADERS,
                follow_redirects=True,
                timeout=30,
            ) as client:
                # ── Phase 1: collect unique products via facet combinations ──────
                products: list[dict] = []
                sku_weight: dict[str, Optional[str]] = {}  # masterSku → known weight

                async def _add_items(items: list[dict], weight_hint: Optional[str] = None) -> None:
                    for item in items:
                        sku = item.get("masterSku", "")
                        if not sku:
                            continue
                        if weight_hint and sku not in sku_weight:
                            sku_weight[sku] = weight_hint
                        if sku not in seen_products:
                            seen_products.add(sku)
                            products.append(item)

                # Weight queries first — so we capture authoritative weight info
                weight_results = await asyncio.gather(*[
                    _query_products(client, [{"facetKey": "yarnWeight", "facetValue": w}])
                    for w in _WEIGHT_FACETS
                ])
                for weight_facet, items in zip(_WEIGHT_FACETS, weight_results):
                    await _add_items(items, _parse_weight_from_facet(weight_facet))

                # Base query
                await _add_items(await _query_products(client, []))

                # Brand queries
                brand_results = await asyncio.gather(*[
                    _query_products(client, [{"facetKey": "brand", "facetValue": b}])
                    for b in _BRAND_FACETS
                ])
                for items in brand_results:
                    await _add_items(items)

                # Brand × weight combinations for deeper coverage
                combos = [
                    (b, w) for b in _BRAND_FACETS for w in _WEIGHT_FACETS
                ]
                combo_results = await asyncio.gather(*[
                    _query_products(client, [
                        {"facetKey": "brand", "facetValue": b},
                        {"facetKey": "yarnWeight", "facetValue": w},
                    ])
                    for b, w in combos
                ])
                for (b, w), items in zip(combos, combo_results):
                    await _add_items(items, _parse_weight_from_facet(w))

                # ── Phase 2: fetch detail pages + extract all color variants ────
                for batch_start in range(0, len(products), BATCH_SIZE):
                    if len(results) >= limit:
                        break
                    batch = products[batch_start:batch_start + BATCH_SIZE]

                    # Build product metadata
                    product_meta = []
                    for item in batch:
                        product_name = item.get("productName", "")
                        master_sku = item.get("masterSku", "")
                        if not product_name or not master_sku:
                            continue
                        price = _parse_price(item)
                        # Use authoritative weight from facet query if available
                        weight = sku_weight.get(master_sku) or infer_weight(product_name)
                        fiber = infer_fiber(product_name)
                        url = f"{self.base_url}/product/{_slug(product_name)}-{master_sku}"

                        vm_raw = item.get("variantCountMap", "{}")
                        vm = json.loads(vm_raw) if isinstance(vm_raw, str) else vm_raw or {}
                        total_colors = vm.get("Color", 0)

                        subs_raw = item.get("subSkusWithColor", "[]")
                        subs = json.loads(subs_raw) if isinstance(subs_raw, str) else subs_raw or []

                        product_meta.append((url, product_name, price, weight, fiber, total_colors, subs))

                    # Fetch detail pages concurrently for this batch
                    page_resps = await asyncio.gather(*[
                        client.get(url) for url, *_ in product_meta
                    ], return_exceptions=True)

                    yarn_tasks = []
                    for (url, product_name, price, weight, fiber, total_colors, subs), resp in zip(
                        product_meta, page_resps
                    ):
                        if len(results) + len(yarn_tasks) >= limit:
                            break

                        # Get color → swatch map: prefer detail page (all colors),
                        # fall back to search API's 4 subs
                        color_map: dict[str, Optional[str]] = {}
                        if not isinstance(resp, Exception) and resp.status_code == 200:
                            color_map = _parse_swatch_urls(resp.text)

                        if not color_map and subs:
                            for sub in subs:
                                cn = sub.get("colorName", "").strip()
                                if cn:
                                    color_map[cn] = (
                                        sub.get("fullSizeUrl") or sub.get("swatchImageUrl")
                                    )

                        for color_name, swatch_url in color_map.items():
                            if len(results) + len(yarn_tasks) >= limit:
                                break
                            if not color_name or not _is_solid(color_name):
                                continue
                            key = f"{url}|{color_name}"
                            if key in seen_colors:
                                continue
                            seen_colors.add(key)
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

                    for i in range(0, len(yarn_tasks), BATCH_SIZE):
                        batch2 = await asyncio.gather(*yarn_tasks[i:i + BATCH_SIZE])
                        results.extend(batch2)

        except Exception:
            pass

        return results[:limit]
