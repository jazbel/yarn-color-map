import hashlib
from pathlib import Path
from typing import Any, Optional
from color_utils import color_name_to_hex, closest_color_family, hex_to_rgb, extract_dominant_color

IMAGES_DIR = Path(__file__).parent.parent / "images"

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

    async def scrape(self, limit: int = 5000) -> list[dict[str, Any]]:
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
        fiber: Optional[str] = None,
        price: Optional[str] = None,
        extract_image_color: bool = False,
    ) -> dict[str, Any]:
        color_source = "name"
        local_image_path: Optional[str] = None
        if not hex_color and image_url and extract_image_color:
            ext = Path(image_url.split("?")[0]).suffix
            if not ext or len(ext) > 5:
                ext = ".jpg"
            fname = hashlib.md5(image_url.encode()).hexdigest() + ext
            save_path = IMAGES_DIR / fname
            local_image_path = f"/images/{fname}"
            extracted = await extract_dominant_color(image_url, save_path=save_path)
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
            "color_source": color_source,
            "color_family": closest_color_family(r, g, b),
            "store": self.name,
            "store_id": self.store_id,
            "url": url,
            "image_url": image_url,
            "local_image_path": local_image_path,
            "brand": brand or self.name,
            "weight": weight,
            "fiber": fiber,
            "price": price,
        }
