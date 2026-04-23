import re
import io
import colorsys
from typing import Optional, Tuple

import httpx
from PIL import Image

# Comprehensive yarn color name → hex mapping
YARN_COLOR_MAP: dict[str, str] = {
    # Whites & near-whites
    "white": "#FFFFFF", "snow white": "#FFFAFA", "bright white": "#F8F8FF",
    "crisp white": "#F9F9F9", "optical white": "#F5F5F5", "ivory": "#FFFFF0",
    "antique white": "#FAEBD7", "warm white": "#FFF8E7", "cream": "#FFFDD0",
    "natural white": "#F5F5DC", "natural": "#F5F5DC", "off white": "#FAF0E6",
    "off-white": "#FAF0E6", "ecru": "#C2B280", "linen": "#FAF0E6",
    "pearl": "#F0EAD6", "chalk": "#F2F2EE", "porcelain": "#F5F0E8",
    "eggshell": "#F0EAD6", "vanilla": "#F3E5AB", "butter": "#FFFACD",
    "snow": "#FFFAFA", "flax": "#EEDC82", "oatmeal": "#E8DCC8",

    # Blacks & dark neutrals
    "black": "#000000", "jet black": "#0A0A0A", "ebony": "#2C2C2C",
    "onyx": "#353839", "coal": "#1A1A1A", "charcoal": "#36454F",
    "dark charcoal": "#2C3539", "graphite": "#474A51",

    # Grays
    "gray": "#808080", "grey": "#808080", "light gray": "#D3D3D3",
    "light grey": "#D3D3D3", "medium gray": "#9E9E9E", "medium grey": "#9E9E9E",
    "dark gray": "#404040", "dark grey": "#404040", "silver": "#C0C0C0",
    "silver gray": "#BFC1C2", "stone": "#928E85", "pebble": "#9E9E8E",
    "dove": "#D5D2CA", "dove gray": "#C7C2BB", "fog": "#B2B2B4",
    "mist": "#C4C8C9", "haze": "#C9C9C3", "steel": "#708090",
    "steel gray": "#717B7F", "storm": "#5C6670", "slate": "#708090",
    "ash": "#B2BEB5", "smoke": "#738276", "pewter": "#96A8A1",

    # Reds
    "red": "#CC0000", "bright red": "#FF1744", "true red": "#CC0000",
    "deep red": "#8B0000", "dark red": "#8B0000", "crimson": "#DC143C",
    "scarlet": "#FF2400", "ruby": "#9B111E", "garnet": "#733635",
    "burgundy": "#800020", "wine": "#722F37", "bordeaux": "#5C1A1A",
    "oxblood": "#4A0000", "cherry": "#DE3163", "cherry red": "#C40000",
    "tomato": "#FF6347", "tomato red": "#CE2939", "poppy": "#FF4136",
    "poppy red": "#E8372A", "brick": "#CB4154", "brick red": "#A52A2A",
    "apple": "#FF4C4C", "apple red": "#C0392B", "barn red": "#7C0A02",
    "mars red": "#C1440E", "cadmium red": "#E30022",

    # Pinks
    "pink": "#FFC0CB", "light pink": "#FFB6C1", "hot pink": "#FF69B4",
    "deep pink": "#FF1493", "bright pink": "#FF0090", "candy pink": "#E4717A",
    "flamingo": "#FC8EAC", "flamingo pink": "#F7A8B8", "rose": "#FF007F",
    "rose pink": "#FF66B2", "old rose": "#C08081", "dusty rose": "#C99A9A",
    "blush": "#DE5D83", "blush pink": "#F4A7B9", "ballet pink": "#F2A7B3",
    "soft pink": "#FFB3BA", "baby pink": "#F4C2C2", "powder pink": "#FFD1DC",
    "pale pink": "#FADADD", "bubblegum": "#FE7BBF", "raspberry": "#E30B5C",
    "fuchsia": "#FF00FF", "magenta": "#FF00FF", "cerise": "#DE3163",
    "watermelon": "#FC6C85", "peony": "#FF5E7E", "carnation": "#FFA6C9",
    "millennial pink": "#E8A0A0", "dusty pink": "#D9A0A0", "mauve": "#E0B0FF",
    "antique rose": "#C29587", "vintage rose": "#C28080", "rosy brown": "#BC8F8F",

    # Oranges
    "orange": "#FF7F00", "bright orange": "#FF6600", "deep orange": "#FF3D00",
    "dark orange": "#FF8C00", "burnt orange": "#CC5500", "tangerine": "#F28500",
    "mandarin": "#F37A48", "clementine": "#E96A24", "pumpkin": "#FF7518",
    "amber": "#FFBF00", "rust": "#B7410E", "terra cotta": "#E2725B",
    "terracotta": "#E2725B", "copper": "#B87333", "bronze": "#CD7F32",
    "sienna": "#A0522D", "burnt sienna": "#E97451", "canyon": "#CA6641",
    "clay": "#C46210", "apricot": "#FBCEB1", "peach": "#FFCBA4",
    "salmon": "#FA8072", "coral": "#FF7F50", "coral pink": "#F88379",
    "melon": "#FDBCB4", "papaya": "#FFEFD5", "persimmon": "#EC5800",
    "cayenne": "#B14A28", "harvest": "#DA8A67",

    # Yellows
    "yellow": "#FFD700", "bright yellow": "#FFEE00", "lemon": "#FFF44F",
    "lemon yellow": "#F5F52A", "canary": "#FFEF00", "golden": "#FFD700",
    "gold": "#FFD700", "sunflower": "#FFDA29", "sunshine": "#FFF700",
    "saffron": "#F4C430", "mustard": "#FFDB58", "ochre": "#CC7722",
    "daffodil": "#FFFF31", "buttercup": "#F3AD16", "banana": "#FFE135",
    "corn": "#FBEC5D", "straw": "#E4D96F", "hay": "#D4B896",
    "wheat": "#F5DEB3", "champagne": "#F7E7CE", "pale yellow": "#FFFFE0",
    "goldenrod": "#DAA520", "maize": "#FBEC5D", "sunglow": "#FFCC33",
    "citrus": "#F5E642",

    # Greens
    "green": "#228B22", "bright green": "#66FF00", "lime": "#32CD32",
    "lime green": "#32CD32", "neon green": "#39FF14", "forest": "#228B22",
    "forest green": "#228B22", "hunter": "#355E3B", "hunter green": "#355E3B",
    "dark green": "#006400", "deep green": "#004B23", "bottle green": "#006A4E",
    "emerald": "#50C878", "emerald green": "#009B77", "kelly": "#4CBB17",
    "kelly green": "#4CBB17", "shamrock": "#00A550", "shamrock green": "#009E60",
    "olive": "#808000", "olive green": "#6B8E23", "army green": "#4B5320",
    "military green": "#4B5320", "moss": "#8A9A5B", "moss green": "#678C4C",
    "sage": "#BCB88A", "sage green": "#8FBD8B", "fern": "#4F7942",
    "fern green": "#4F7942", "mint": "#98FF98", "mint green": "#98FF98",
    "seafoam": "#93E9BE", "seafoam green": "#71BC78", "spearmint": "#00FA9A",
    "jade": "#00A86B", "jade green": "#00A86B", "teal": "#008080",
    "pine": "#2E4F2E", "pine green": "#01796F", "spruce": "#4A7856",
    "avocado": "#568203", "basil": "#5B6E41", "celery": "#B8C99A",
    "pistachio": "#93C572", "apple green": "#8DB600", "chartreuse": "#7FFF00",
    "pear": "#C9CC3F", "wasabi": "#788F33", "eucalyptus": "#44D7A8",
    "juniper": "#3A5F52", "verdant": "#6A9955", "meadow": "#52A54B",
    "grasshopper": "#5CAD4A", "artichoke": "#8F9779", "willow": "#A2AD91",

    # Blues
    "blue": "#0047AB", "bright blue": "#0066FF", "true blue": "#0073CF",
    "royal": "#4169E1", "royal blue": "#4169E1", "cobalt": "#0047AB",
    "cobalt blue": "#0047AB", "navy": "#000080", "navy blue": "#000080",
    "dark navy": "#0D0D2B", "midnight": "#191970", "midnight blue": "#191970",
    "indigo": "#4B0082", "deep blue": "#003399", "ocean": "#006994",
    "ocean blue": "#006994", "sea": "#2E8B57", "sea blue": "#0E5C8A",
    "sapphire": "#0F52BA", "sapphire blue": "#0F52BA",
    "cornflower": "#6495ED", "cornflower blue": "#6495ED",
    "periwinkle": "#CCCCFF", "sky": "#87CEEB", "sky blue": "#87CEEB",
    "baby blue": "#89CFF0", "light blue": "#ADD8E6", "powder blue": "#B0E0E6",
    "ice blue": "#D4F1F9", "slate blue": "#6A5ACD", "denim": "#1560BD",
    "denim blue": "#1560BD", "electric blue": "#7DF9FF",
    "cerulean": "#007BA7", "azure": "#007FFF", "pacific": "#1CA9C9",
    "aqua": "#00FFFF", "cyan": "#00FFFF", "aquamarine": "#7FFFD4",
    "turquoise": "#40E0D0", "dark turquoise": "#00CED1", "teal blue": "#367588",
    "glacier": "#80B9C4", "pool": "#36A8BF", "lagoon": "#0077BE",
    "tide": "#4E8B9A", "river": "#5B8A99", "carolina blue": "#56A0D3",
    "atlantic": "#1C4E80", "ice": "#D0E8F0", "nordic": "#3B6FAA",
    "steel blue": "#4682B4",

    # Purples
    "purple": "#800080", "bright purple": "#8F00FF", "deep purple": "#36013F",
    "dark purple": "#4B0082", "violet": "#EE82EE", "dark violet": "#9400D3",
    "grape": "#6F2DA8", "plum": "#DDA0DD", "dark plum": "#592424",
    "amethyst": "#9966CC", "orchid": "#DA70D6", "lavender": "#E6E6FA",
    "dark lavender": "#967BB6", "heather": "#B695C0", "lilac": "#C8A2C8",
    "wisteria": "#C9A0DC", "thistle": "#D8BFD8", "mulberry": "#C54B8C",
    "eggplant": "#614051", "aubergine": "#614051", "iris": "#5A4FCF",
    "hyacinth": "#7C7BBE", "dusty purple": "#9B7EBD", "soft purple": "#C3A1C8",
    "boysenberry": "#873260", "ultraviolet": "#5F4B8B", "byzantium": "#702963",

    # Browns
    "brown": "#A52A2A", "dark brown": "#654321", "chocolate": "#7B3F00",
    "chocolate brown": "#5C3317", "coffee": "#6F4E37", "mocha": "#967969",
    "espresso": "#3C2415", "caramel": "#C68642", "chestnut": "#954535",
    "walnut": "#6D3B2A", "cinnamon": "#D2691E", "spice": "#9E5330",
    "nutmeg": "#8B5130", "toffee": "#A07040", "camel": "#C19A6B",
    "tan": "#D2B48C", "sand": "#C2B280", "sandy": "#F4A460",
    "sandy brown": "#F4A460", "beige": "#F5F5DC", "warm beige": "#E8D5B7",
    "taupe": "#483C32", "dark taupe": "#2B1D0E", "khaki": "#C3B091",
    "driftwood": "#AF8554", "oak": "#806517", "mahogany": "#C04000",
    "russet": "#80461B", "umber": "#635147", "sepia": "#704214",
    "leather": "#9B5523", "adobe": "#CA6540", "prairie": "#B5924C",
    "cedar": "#A0522D", "ginger": "#B06500", "butterscotch": "#E3963E",
    "praline": "#B87B60", "latte": "#C5A880", "mushroom": "#C8B89A",
    "fawn": "#E5AA70", "biscuit": "#D4AC76",

    # Teals
    "dark teal": "#003333", "light teal": "#007C8A",
    "seafoam teal": "#3FC1C9", "aqua teal": "#00B5CC", "jade teal": "#00A878",

    # Special names
    "multi": "#888888", "multicolor": "#888888", "variegated": "#888888",
    "ombre": "#888888", "gradient": "#888888", "speckled": "#888888",
    "marled": "#888888", "heathered": "#888888", "mottled": "#888888",
    "tweed": "#888888",
}


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def closest_color_family(r: int, g: int, b: int) -> str:
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if v > 0.85 and s < 0.25:
        return "white"
    if v < 0.15:
        return "black"
    if s < 0.15:
        return "gray" if v > 0.25 else "black"
    # Dark, low-saturation colors (charcoal, slate, dark blue-gray)
    if v < 0.45 and s < 0.40:
        return "gray"
    hue = h * 360
    if hue < 15 or hue >= 345:
        return "red"
    elif hue < 45:
        return "orange"
    elif hue < 75:
        return "yellow"
    elif hue < 150:
        return "green"
    elif hue < 200:
        return "teal"
    elif hue < 255:
        return "blue"
    elif hue < 285:
        return "purple"
    else:
        return "pink"


def color_name_to_hex(name: str) -> str:
    if not name:
        return "#888888"
    key = name.lower().strip()
    key = re.sub(r"\s+", " ", key)

    if key in YARN_COLOR_MAP:
        return YARN_COLOR_MAP[key]

    # Longest substring match first
    for candidate in sorted(YARN_COLOR_MAP, key=len, reverse=True):
        if candidate in key:
            return YARN_COLOR_MAP[candidate]

    # Word-by-word, reverse order (last word often most descriptive)
    words = re.split(r"[\s\-_/]+", key)
    for word in reversed(words):
        if word in YARN_COLOR_MAP:
            return YARN_COLOR_MAP[word]

    return "#888888"


def dominant_color_from_bytes(data: bytes) -> Optional[str]:
    """
    Extract the dominant yarn color from raw image bytes.

    Uses PIL median-cut quantization to cluster the image into 16 palette
    colors, then scores each cluster by (pixel_count * (1 + saturation*2.5))
    so that colorful yarn pixels win over white backgrounds and gray shadows.
    """
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None

    img = img.resize((120, 120), Image.LANCZOS)

    # Median-cut quantize → 16 representative colors
    q = img.quantize(colors=16)
    pal = q.getpalette()          # flat [R,G,B, R,G,B, ...] for up to 256 entries
    counts: dict[int, int] = {}
    for idx in q.getdata():
        counts[idx] = counts.get(idx, 0) + 1

    scored: list[tuple[float, int, int, int]] = []
    for idx, cnt in counts.items():
        r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]

        # Skip pure-white / near-white backgrounds
        if r > 235 and g > 235 and b > 235:
            continue
        # Skip near-black shadows / borders
        if r < 20 and g < 20 and b < 20:
            continue

        _, s, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        # Weight by saturation so "real" yarn colors beat muddy grays
        scored.append((cnt * (1.0 + s * 2.5), r, g, b))

    if scored:
        scored.sort(reverse=True)
        _, r, g, b = scored[0]
        return f"#{r:02X}{g:02X}{b:02X}"

    # Fallback: average all non-pure-white pixels
    pixels = [p for p in img.getdata() if not (p[0] > 245 and p[1] > 245 and p[2] > 245)]
    if not pixels:
        pixels = list(img.getdata())
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return f"#{r:02X}{g:02X}{b:02X}"


async def extract_dominant_color(image_url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={"Accept": "image/webp,image/*,*/*"},
        ) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                return None
        return dominant_color_from_bytes(resp.content)
    except Exception:
        return None
