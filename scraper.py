"""
Apple Refurbished Store Monitor
===============================
Scrapes Apple's refurbished product pages using the embedded JSON-LD
structured data (schema.org Product markup). Compares current products
against a saved state and sends ntfy.sh push notifications for any
newly added products.

Runs via GitHub Actions every 15 minutes.
"""

import requests
import json
import os
import re
import sys
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

SITES = [
    {
        "name": "Refurbished Mac Mini",
        "url": "https://www.apple.com/ca/shop/refurbished/mac/mac-mini",
    },
    {
        "name": "Refurbished Mac (All)",
        "url": "https://www.apple.com/ca/shop/refurbished/mac",
    },
]

# Telegram Bot — set via GitHub Secrets or environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

STATE_FILE = "sites_state.json"

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def load_state() -> dict:
    """Load previously seen products from state file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """Persist current product state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def extract_products(html: str) -> dict:
    """
    Parse all JSON-LD <script type="application/ld+json"> blocks from the
    page HTML. Returns a dict keyed by SKU with product details.
    
    Apple embeds schema.org Product objects with name, sku, price, url,
    description, and color for every refurbished product on the page.
    """
    products = {}

    # Find all JSON-LD script blocks
    pattern = r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL)

    for raw_json in matches:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        # Only process Product entries
        if data.get("@type") != "Product":
            continue

        # Extract the SKU from the offers array
        offers = data.get("offers", [])
        if not offers:
            continue

        offer = offers[0] if isinstance(offers, list) else offers
        sku = offer.get("sku", "")
        if not sku:
            continue

        price = offer.get("price", 0)
        currency = offer.get("priceCurrency", "CAD")

        products[sku] = {
            "name": data.get("name", "Unknown Product"),
            "sku": sku,
            "price": float(price),
            "currency": currency,
            "url": data.get("url", ""),
            "description": data.get("description", ""),
            "color": data.get("color", ""),
        }

    return products


def send_notification(title: str, message: str, url: str = "", tags: str = "") -> None:
    """Send a push notification via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  x Telegram credentials not set (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return

    text = f"*{title}*\n\n{message}"
    if url:
        text += f"\n\n[Open on Apple.com]({url})"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            print(f"  -> Telegram notification sent")
        else:
            print(f"  x Telegram error: {data.get('description', resp.status_code)}")
    except Exception as e:
        print(f"  x Failed to send notification: {e}")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────


def main():
    state = load_state()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    any_changes = False

    print(f"=== Apple Refurbished Monitor — {now} ===\n")

    for site in SITES:
        site_name = site["name"]
        site_url = site["url"]
        # Use a stable key for the state dict
        site_key = site_url

        print(f"Checking: {site_name}")
        print(f"  URL: {site_url}")

        try:
            response = requests.get(site_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  ✗ Failed to fetch page: {e}")
            continue

        current_products = extract_products(response.text)
        print(f"  Found {len(current_products)} products on page")

        if not current_products:
            print("  ⚠ No products found — page may have changed structure")
            continue

        # Get previously seen SKUs for this site
        previous_skus = set(state.get(site_key, {}).get("skus", []))
        previous_products = state.get(site_key, {}).get("products", {})
        current_skus = set(current_products.keys())

        # Determine new, removed, and price-changed products
        new_skus = current_skus - previous_skus
        removed_skus = previous_skus - current_skus
        common_skus = current_skus & previous_skus

        # Check for price changes on existing products
        price_changed = []
        for sku in common_skus:
            old_price = previous_products.get(sku, {}).get("price")
            new_price = current_products[sku]["price"]
            if old_price is not None and old_price != new_price:
                price_changed.append({
                    "sku": sku,
                    "name": current_products[sku]["name"],
                    "old_price": old_price,
                    "new_price": new_price,
                    "url": current_products[sku]["url"],
                })

        # ── NEW PRODUCTS ──
        if new_skus:
            any_changes = True
            print(f"  🆕 {len(new_skus)} NEW product(s)!")

            for sku in sorted(new_skus):
                product = current_products[sku]
                price_str = f"${product['price']:,.2f} {product['currency']}"
                print(f"    + {product['name']} — {price_str}")
                print(f"      SKU: {sku}")
                print(f"      URL: {product['url']}")

            if len(new_skus) <= 5:
                for sku in sorted(new_skus):
                    p = current_products[sku]
                    title = f"New: {p['name']}"
                    message = (
                        f"${p['price']:,.2f} {p['currency']}\n"
                        f"SKU: {p['sku']}\n"
                        f"Color: {p['color']}\n"
                        f"Source: {site_name}"
                    )
                    send_notification(title, message, url=p["url"], tags="apple,package,tada")
            else:
                title = f"{len(new_skus)} new products on {site_name}!"
                lines = []
                for i, sku in enumerate(sorted(new_skus)):
                    if i >= 10:
                        lines.append(f"... and {len(new_skus) - 10} more")
                        break
                    p = current_products[sku]
                    lines.append(f"{p['name']} - ${p['price']:,.2f}")
                message = "\n".join(lines)
                send_notification(title, message, url=site_url, tags="apple,package,tada")

        # ── REMOVED PRODUCTS (sold out) ──
        if removed_skus:
            any_changes = True
            print(f"  🗑️  {len(removed_skus)} product(s) SOLD OUT / removed")

            for sku in sorted(removed_skus):
                old = previous_products.get(sku, {})
                name = old.get("name", sku)
                price = old.get("price", 0)
                print(f"    - {name} — ${price:,.2f}")

            if len(removed_skus) <= 5:
                for sku in sorted(removed_skus):
                    old = previous_products.get(sku, {})
                    name = old.get("name", sku)
                    price = old.get("price", 0)
                    title = f"Sold out: {name}"
                    message = (
                        f"Was ${price:,.2f} CAD\n"
                        f"SKU: {sku}\n"
                        f"Source: {site_name}"
                    )
                    send_notification(title, message, url=site_url, tags="apple,rotating_light")
            else:
                title = f"{len(removed_skus)} products sold out on {site_name}"
                lines = []
                for i, sku in enumerate(sorted(removed_skus)):
                    if i >= 10:
                        lines.append(f"... and {len(removed_skus) - 10} more")
                        break
                    old = previous_products.get(sku, {})
                    lines.append(f"{old.get('name', sku)} - was ${old.get('price', 0):,.2f}")
                message = "\n".join(lines)
                send_notification(title, message, url=site_url, tags="apple,rotating_light")

        # ── PRICE CHANGES ──
        if price_changed:
            any_changes = True
            print(f"  💰 {len(price_changed)} product(s) changed price!")

            for pc in price_changed:
                direction = "↓" if pc["new_price"] < pc["old_price"] else "↑"
                print(f"    {direction} {pc['name']} — ${pc['old_price']:,.2f} → ${pc['new_price']:,.2f}")

            for pc in price_changed:
                diff = pc["new_price"] - pc["old_price"]
                if diff < 0:
                    title = f"Price drop: {pc['name']}"
                    tags = "apple,chart_with_downwards_trend,tada"
                else:
                    title = f"Price increase: {pc['name']}"
                    tags = "apple,chart_with_upwards_trend"
                message = (
                    f"Was: ${pc['old_price']:,.2f} CAD\n"
                    f"Now: ${pc['new_price']:,.2f} CAD\n"
                    f"Change: {'−' if diff < 0 else '+'}${abs(diff):,.2f}\n"
                    f"Source: {site_name}"
                )
                send_notification(title, message, url=pc["url"], tags=tags)

        if not new_skus and not removed_skus and not price_changed:
            print("  ✓ No changes")

        # Update state for this site
        state[site_key] = {
            "skus": sorted(current_skus),
            "last_checked": now,
            "product_count": len(current_products),
            "products": {
                sku: {
                    "name": p["name"],
                    "price": p["price"],
                    "color": p["color"],
                }
                for sku, p in current_products.items()
            },
        }

        print()

    save_state(state)
    print(f"State saved to {STATE_FILE}")

    if not any_changes:
        print("\nNo changes found across all sites.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
