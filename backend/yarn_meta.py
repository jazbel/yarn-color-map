"""
Utilities for extracting yarn fiber content and weight from product titles,
descriptions, and explicit weight strings.
"""
import re
from typing import Optional

# ── Weight ────────────────────────────────────────────────────────────────────

# Ordered from lightest to heaviest (used for sorting / display)
WEIGHT_ORDER = [
    "Lace", "Fingering", "Sport", "DK", "Worsted",
    "Aran", "Bulky", "Super Bulky", "Jumbo",
]

# Maps various spellings / notations → canonical weight name
_WEIGHT_ALIASES: list[tuple[re.Pattern, str]] = [
    # Explicit standard names first
    (re.compile(r'\bjumbo\b',        re.I), "Jumbo"),
    (re.compile(r'\bsuper[\s\-]?bulky\b', re.I), "Super Bulky"),
    (re.compile(r'\bbulky\b',        re.I), "Bulky"),
    (re.compile(r'\bchunky\b',       re.I), "Bulky"),
    (re.compile(r'\baran\b',         re.I), "Aran"),
    (re.compile(r'\bworsted\b',      re.I), "Worsted"),
    (re.compile(r'\bdk\b',           re.I), "DK"),
    (re.compile(r'\bdouble\s?knit\b',re.I), "DK"),
    (re.compile(r'\bsport\b',        re.I), "Sport"),
    (re.compile(r'\bfingering\b',    re.I), "Fingering"),
    (re.compile(r'\bsock\b',         re.I), "Fingering"),
    (re.compile(r'\blace\b',         re.I), "Lace"),
    # Danish/European Nm notation  e.g. "8/4", "8/8", "6/2", "4/8"
    # Rule of thumb: multiply the two numbers → if ≥ 40 → Lace/Fine
    # Common Hobbii mappings:
    (re.compile(r'\b8/4\b'),  "DK"),
    (re.compile(r'\b8/6\b'),  "Worsted"),
    (re.compile(r'\b8/8\b'),  "Bulky"),
    (re.compile(r'\b6/2\b'),  "Fingering"),
    (re.compile(r'\b4/8\b'),  "Bulky"),
    (re.compile(r'\b2/8\b'),  "Lace"),
    (re.compile(r'\b3/9\b'),  "Aran"),
    (re.compile(r'\b3mm\b',   re.I), "DK"),
    (re.compile(r'\b5mm\b',   re.I), "Bulky"),
    # Weight numbers (CYC / Craft Yarn Council standard 0-7)
    (re.compile(r'\bweight\s*0\b',  re.I), "Lace"),
    (re.compile(r'\bweight\s*1\b',  re.I), "Fingering"),
    (re.compile(r'\bweight\s*2\b',  re.I), "Sport"),
    (re.compile(r'\bweight\s*3\b',  re.I), "DK"),
    (re.compile(r'\bweight\s*4\b',  re.I), "Worsted"),
    (re.compile(r'\bweight\s*5\b',  re.I), "Bulky"),
    (re.compile(r'\bweight\s*6\b',  re.I), "Super Bulky"),
    (re.compile(r'\bweight\s*7\b',  re.I), "Jumbo"),
    # XL / XXL hints
    (re.compile(r'\bxl\b',          re.I), "Bulky"),
    (re.compile(r'\bxxl\b',         re.I), "Super Bulky"),
]

def infer_weight(title: str, description: str = "", weight_hint: str = "") -> Optional[str]:
    """Return canonical weight name from any combination of title / description / hint."""
    sources = [weight_hint, title, description]
    for src in sources:
        if not src:
            continue
        for pattern, canonical in _WEIGHT_ALIASES:
            if pattern.search(src):
                return canonical
    return None


# ── Fiber ─────────────────────────────────────────────────────────────────────

FIBER_ORDER = [
    "Cotton", "Wool", "Merino", "Alpaca", "Mohair",
    "Acrylic", "Nylon", "Polyester",
    "Bamboo", "Silk", "Linen", "Cashmere", "Blend",
]

_FIBER_ALIASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bcashmere\b',                re.I), "Cashmere"),
    (re.compile(r'\bsilk\b',                    re.I), "Silk"),
    (re.compile(r'\bmohair\b',                  re.I), "Mohair"),
    (re.compile(r'\balpaca\b',                  re.I), "Alpaca"),
    (re.compile(r'\bmerino\b',                  re.I), "Merino"),
    (re.compile(r'\bwool\b',                    re.I), "Wool"),
    (re.compile(r'\blamb[s\']?wool\b',          re.I), "Wool"),
    (re.compile(r'\bshetland\b',                re.I), "Wool"),
    (re.compile(r'\bcotton\b',                  re.I), "Cotton"),
    (re.compile(r'\bbamboo\b',                  re.I), "Bamboo"),
    (re.compile(r'\blinen\b',                   re.I), "Linen"),
    (re.compile(r'\bhemp\b',                    re.I), "Linen"),
    (re.compile(r'\bnylon\b',                   re.I), "Nylon"),
    (re.compile(r'\bpolyamide\b',               re.I), "Nylon"),
    (re.compile(r'\bpolyester\b',               re.I), "Polyester"),
    (re.compile(r'\bacrylic\b',                 re.I), "Acrylic"),
    (re.compile(r'\bhb\s+acrylic\b',            re.I), "Acrylic"),
    (re.compile(r'\bmicrofibre\b',              re.I), "Acrylic"),
    (re.compile(r'\b100\s*%\s*acrylic\b',       re.I), "Acrylic"),
]

def infer_fiber(title: str, description: str = "") -> Optional[str]:
    """Return the primary fiber from title + description HTML/text."""
    # Strip basic HTML tags from description
    desc_clean = re.sub(r'<[^>]+>', ' ', description)
    sources = [title, desc_clean]
    for src in sources:
        for pattern, canonical in _FIBER_ALIASES:
            if pattern.search(src):
                return canonical
    return None


def strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html)
