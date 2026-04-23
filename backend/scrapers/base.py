from typing import Any, Optional
from color_utils import color_name_to_hex, closest_color_family, hex_to_rgb, extract_dominant_color

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class BaseScraper:
    store_id: str = "unknown"
    name: str = "Unknown Store"
    base_url: str = ""

    async def scrape(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def make_yarn(
        self,
        *,
        product_name: str,
        color_name: str,
        url: str,
        image_url: Optional[str] = None,
        hex_color: Optional[str] = None,
        brand: Optional[str] = None,
        weight: Optional[str] = None,
        price: Optional[str] = None,
        extract_image_color: bool = False,
    ) -> dict[str, Any]:
        color_source = "name"
        if not hex_color and image_url and extract_image_color:
            extracted = await extract_dominant_color(image_url)
            if extracted:
                hex_color = extracted
                color_source = "image"
        if not hex_color:
            hex_color = color_name_to_hex(color_name)

        r, g, b = hex_to_rgb(hex_color)
        return {
            "id": f"{self.store_id}-{abs(hash(url + color_name)) % 1_000_000:06d}",
            "product_name": product_name,
            "color_name": color_name,
            "hex_color": hex_color,
            "color_source": color_source,   # "image" or "name"
            "color_family": closest_color_family(r, g, b),
            "store": self.name,
            "store_id": self.store_id,
            "url": url,
            "image_url": image_url,
            "brand": brand or self.name,
            "weight": weight,
            "price": price,
        }
