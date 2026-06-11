# Apple Refurbished Monitor 🍎

Monitors Apple Canada's refurbished store for new product listings and sends push notifications via [ntfy.sh](https://ntfy.sh).

## What it does

- Scrapes [Refurbished Mac Mini](https://www.apple.com/ca/shop/refurbished/mac/mac-mini) and [Refurbished Mac (All)](https://www.apple.com/ca/shop/refurbished/mac) every **15 minutes** via GitHub Actions
- Parses the embedded **JSON-LD structured data** (schema.org Product markup) — much more reliable than HTML scraping
- Tracks products by **SKU** — detects genuinely new products, not just page layout changes
- Sends **push notifications** with product name, price, color, and a direct link to buy

## Get notifications on your phone

1. Install the [ntfy app](https://ntfy.sh) on your phone (iOS / Android)
2. Subscribe to the topic: **`apple_mac_mini`**
3. Done! You'll get a notification whenever new refurbished products appear

## How it works

```
Apple Page → JSON-LD extraction → Compare SKUs → ntfy.sh notification
                                       ↓
                              sites_state.json (committed to repo)
```

## Run locally

```bash
pip install requests
python scraper.py
```

## Files

| File | Purpose |
|------|---------|
| `scraper.py` | Main scraper script |
| `sites_state.json` | Persisted product state (auto-generated) |
| `.github/workflows/monitor.yml` | GitHub Actions cron schedule (every 15 min) |