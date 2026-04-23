# Yarn Color Map

Scrapes solid-color yarn from **Hobbii**, **LoveCrafts**, and **Knit Picks**, extracts the RGB hex code from each product image, and displays everything in a searchable, filterable web UI.

---

## How it works

| Step | What happens |
|------|-------------|
| 1 | The backend scrapes each store's product catalog |
| 2 | For each color variant it downloads the product image (300 px) |
| 3 | PIL median-cut quantization extracts the dominant yarn color |
| 4 | The hex code + image URL are stored in a local cache (`yarn_cache.json`) |
| 5 | The frontend fetches the cache and renders each yarn with its photo and hex overlay |

**Hobbii** uses the Shopify products JSON API (`/collections/yarn/products.json`), which returns per-variant `featured_image` URLs — one photo per color. The other stores fall back to comprehensive seed data when live scraping is blocked.

---

## Requirements

- Python 3.9+
- pip3

---

## Setup

```bash
cd yarn-color-map/backend
pip3 install -r requirements.txt
```

`requirements.txt` installs:
- `fastapi` + `uvicorn` — web server
- `httpx` — async HTTP client for scraping
- `beautifulsoup4` + `lxml` — HTML parsing
- `Pillow` — image color extraction

---

## Run the server

```bash
cd yarn-color-map/backend
python3 main.py
```

Open **http://localhost:8000** in your browser.

On first load the server scrapes all three stores automatically and caches the results. Subsequent loads are instant (served from cache).

---

## Scraping

### Automatic (on first load)

Just open the app. If `yarn_cache.json` does not exist the server scrapes everything before returning results. Hobbii has ~5 000 color variants so the first scrape takes a few minutes.

### Manual refresh via the UI

Click **↻ Refresh** in the top-right corner of the app.

### Manual refresh via the API

Refresh all stores:
```bash
curl -X POST http://localhost:8000/api/refresh
```

Refresh one store:
```bash
curl -X POST "http://localhost:8000/api/refresh?store=hobbii"
curl -X POST "http://localhost:8000/api/refresh?store=lovecrafts"
curl -X POST "http://localhost:8000/api/refresh?store=knitpicks"
```

Clear the cache entirely and force a full re-scrape on next load:
```bash
curl -X DELETE http://localhost:8000/api/cache
# or just delete the file:
rm yarn-color-map/backend/yarn_cache.json
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/yarns` | List yarns. Supports `store`, `color_family`, `search`, `limit`, `offset` |
| `GET` | `/api/stores` | List available stores |
| `GET` | `/api/color-families` | List color family names |
| `POST` | `/api/refresh` | Re-scrape (optional `?store=` param) |
| `DELETE` | `/api/cache` | Wipe the cache |

Example — get all blue Hobbii yarns:
```bash
curl "http://localhost:8000/api/yarns?store=hobbii&color_family=blue&limit=50"
```

Each yarn object looks like:
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
  "weight": null,
  "price": "$3.49"
}
```

`color_source` is `"image"` when the hex was extracted from the product photo, or `"name"` when it was mapped from the color name text.

---

## Deploy on a server (Nginx + systemd)

### 1. Create a systemd service

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

### 2. Nginx reverse proxy

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
# Add HTTPS:
sudo certbot --nginx -d yarn.yourdomain.com
```

---

## Project structure

```
yarn-color-map/
├── backend/
│   ├── main.py              # FastAPI app + API routes
│   ├── color_utils.py       # Image extraction + color-name-to-hex mapping
│   ├── yarn_cache.json      # Auto-generated cache (gitignore this)
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
