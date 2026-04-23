# Yarn Color Map

Scrapes solid-color yarn from **Hobbii**, **LoveCrafts**, and **Knit Picks**, extracts the RGB hex code from each product image using PIL color quantization, and displays everything in a searchable, filterable web UI.

---

## How it works

| Step | What happens |
|------|-------------|
| 1 | The scraper fetches each store's product catalog |
| 2 | For each solid color variant it downloads the product image (300 px) |
| 3 | PIL median-cut quantization extracts the dominant yarn color |
| 4 | The hex code, image URL, weight, and fiber are stored in `yarn_cache.json` |
| 5 | The FastAPI server serves the cache through a REST API |
| 6 | The frontend renders each yarn with its photo, hex overlay, and filter chips |

**Hobbii** uses the Shopify products JSON API (`/collections/yarn/products.json`), which returns per-variant `featured_image` URLs — one photo per color. LoveCrafts and Knit Picks use HTML scraping with comprehensive seed data fallback when live scraping is blocked.

---

## Requirements

- Python 3.9+
- pip3

---

## Setup

```bash
git clone https://github.com/jazbel/yarn-color-map.git
cd yarn-color-map/backend
pip3 install -r requirements.txt
```

Dependencies:
- `fastapi` + `uvicorn` — web server
- `httpx` — async HTTP client for scraping
- `beautifulsoup4` + `lxml` — HTML parsing
- `Pillow` — image color extraction

---

## Quickstart

Run the scraper first, then start the server:

```bash
./start.sh
```

Open **http://localhost:8000** in your browser.

### Options

```bash
./start.sh           # scrape (skips already-cached stores), then start server
./start.sh --fresh   # clear cache, scrape everything fresh, then start server
```

---

## Running manually

### 1. Scrape yarn data

```bash
cd backend
python3 scrape.py              # scrape all stores
python3 scrape.py hobbii       # scrape one store only
python3 scrape.py lovecrafts knitpicks
```

The scraper saves `yarn_cache.json` after each store completes, so progress is not lost if interrupted.

### 2. Start the server

```bash
cd backend
python3 main.py
```

Open **http://localhost:8000**.

---

## Refreshing data

### Via the UI

Click **↻ Refresh** in the top-right corner of the app.

### Via the API

```bash
# Refresh all stores
curl -X POST http://localhost:8000/api/refresh

# Refresh one store
curl -X POST "http://localhost:8000/api/refresh?store=hobbii"
curl -X POST "http://localhost:8000/api/refresh?store=lovecrafts"
curl -X POST "http://localhost:8000/api/refresh?store=knitpicks"

# Clear cache (forces full re-scrape on next request)
curl -X DELETE http://localhost:8000/api/cache
```

---

## Filters

The UI sidebar supports filtering by:

| Filter | Values |
|--------|--------|
| Store | Hobbii, LoveCrafts, Knit Picks |
| Color Family | red, pink, orange, yellow, green, teal, blue, purple, gray, white, black |
| Weight | Lace, Fingering, Sport, DK, Worsted, Aran, Bulky, Super Bulky, Jumbo |
| Fiber | Cotton, Wool, Acrylic, Alpaca, Mohair, Linen, Silk, Bamboo, Nylon, Polyester, Cashmere |

The color picker lets you pick any hex color and find the closest-matching yarns by HSV distance.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/yarns` | List yarns (filterable, paginated) |
| `GET` | `/api/stores` | List available stores |
| `GET` | `/api/color-families` | List color family names |
| `GET` | `/api/weights` | List yarn weights in CYC order |
| `GET` | `/api/fibers` | List fiber types |
| `POST` | `/api/refresh` | Re-scrape stores (optional `?store=` param) |
| `DELETE` | `/api/cache` | Wipe `yarn_cache.json` |

### `/api/yarns` query parameters

| Param | Example | Description |
|-------|---------|-------------|
| `store` | `hobbii` | Filter by store ID |
| `color_family` | `blue` | Filter by color family |
| `weight` | `DK` | Filter by yarn weight |
| `fiber` | `Wool` | Filter by fiber type |
| `search` | `cobalt` | Search product name or color name |
| `limit` | `60` | Results per page (default 60) |
| `offset` | `120` | Pagination offset |

Example:
```bash
curl "http://localhost:8000/api/yarns?store=hobbii&color_family=blue&weight=DK&limit=20"
```

### Yarn object shape

```json
{
  "product_name": "Friends Cotton 8/4",
  "color_name": "Cobalt Blue (65)",
  "hex_color": "#3B5BA5",
  "color_source": "image",
  "color_family": "blue",
  "store": "Hobbii",
  "store_id": "hobbii",
  "image_url": "https://cdn.shopify.com/s/.../8-4-65_300x.jpg",
  "url": "https://hobbii.com/products/friends-cotton-8-4",
  "weight": "DK",
  "fiber": "Cotton",
  "price": "$3.49"
}
```

`color_source` is `"image"` when the hex was extracted from the product photo, or `"name"` when it was mapped from the color name string.

---

## Deploy on a server (Nginx + systemd)

### 1. Upload files

```bash
scp -r yarn-color-map user@your-server:/var/www/
ssh user@your-server
cd /var/www/yarn-color-map/backend
pip3 install -r requirements.txt
```

### 2. Pre-populate the cache

```bash
python3 scrape.py
```

### 3. Create a systemd service

```ini
# /etc/systemd/system/yarn-color-map.service
[Unit]
Description=Yarn Color Map
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/yarn-color-map/backend
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yarn-color-map
```

### 4. Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name yarn.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/yarn-color-map /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Add HTTPS
sudo certbot --nginx -d yarn.yourdomain.com
```

---

## Project structure

```
yarn-color-map/
├── start.sh                 # Scrape + start server in one command
├── backend/
│   ├── main.py              # FastAPI app + API routes
│   ├── scrape.py            # Standalone scraper script
│   ├── color_utils.py       # Image color extraction + name-to-hex mapping
│   ├── yarn_meta.py         # Weight and fiber inference from product text
│   ├── yarn_cache.json      # Auto-generated cache (gitignored)
│   ├── requirements.txt
│   └── scrapers/
│       ├── base.py          # BaseScraper + make_yarn()
│       ├── hobbii.py        # Shopify JSON API scraper
│       ├── lovecrafts.py    # HTML scraper + Paintbox/Stylecraft seed data
│       └── knitpicks.py     # HTML scraper + Palette/WOTA seed data
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```
