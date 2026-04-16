#!/usr/bin/env python3
"""
Just Colours -- Google Shopping MASTER Feed Generator
======================================================
Produces a single, complete Google Merchant Center primary feed by calling
the Ecwid REST API directly.  No dependency on the Ecwid-generated XML feed.

Outputs TWO files:
  master_feed.xml           -- Google Shopping / Performance-Max primary feed
  local_inventory_feed.xml  -- Google Local Inventory feed (in-store data)

Required environment variable:
  ECWID_TOKEN   -- your Ecwid private API token  (set as a GitHub Secret)

Optional environment variables (have safe defaults):
  STORE_CODE    -- your Ecwid store ID          (default: 77567544)
  SALE_END_DATE -- ISO-8601 end date for sales  (default: 30 days from now)
  STORE_NAME    -- display name                 (default: Just Colours)

Run locally:
  export ECWID_TOKEN=secret_XXXX
  python3 generate_master_feed.py
"""

import os
import re
import json
import math
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

# ── Configuration ────────────────────────────────────────────────────────────
STORE_ID    = os.environ.get("STORE_CODE",    "77567544")
ECWID_TOKEN = os.environ.get("ECWID_TOKEN",   "")          # injected via GitHub Secret
STORE_NAME  = os.environ.get("STORE_NAME",    "Just Colours")
STORE_URL   = "https://justcolours.co.za"
CURRENCY    = "ZAR
STORE_CODE  = STORE_ID   # used in local inventory feed as the GMC store code

# Sale date window: from now until SALE_END_DATE (or 30 days out if not set)
TZ_OFFSET   = "+02:00"   # South Africa / SAST
_now        = datetime.now(timezone.utc)
_sale_start = _now.strftime(f"%Y-%m-%dT00:00{TZ_OFFSET}")

def _default_sale_end():
    end = _now + timedelta(days=30)
    return end.strftime(f"%Y-%m-%dT23:59{TZ_OFFSET}")

SALE_END    = os.environ.get("SALE_END_DATE", _default_sale_end())

# Local store details (for local inventory feed)
LOCAL_STORE = {
    "store_code":    STORE_CODE,
    "pickup_method": "buy",          # buy | reserve | ship to store | not supported
    "pickup_sla":    "same day",     # same day | next day | 2-day | 3-day | 4-day | 5-day | 6-day | multi-week
}

OUTPUT_SHOPPING   = "master_feed.xml"
OUTPUT_LOCAL_INV  = "local_inventory_feed.xml"

# ── Google product category map ───────────────────────────────────────────────
CATEGORY_MAP = [
    ("FDM Printer",           "499682"),
    ("Resin Printer",         "499682"),
    ("3D Printer",            "499682"),
    ("3D Printing",           "499682"),
    ("Filament",              "5074"),
    ("3D Printer Suppli",     "5074"),
    ("3D Printer Accessor",   "5074"),
    ("3D Pen",                "5074"),
    ("Resin",                 "5074"),
    ("Printer",               "304"),
    ("Scanner",               "304"),
    ("Ink",                   "2314"),
    ("Toner",                 "2314"),
    ("Cartridge",             "2314"),
    ("Print Head",            "2314"),
    ("Ribbon",                "2314"),
    ("Laser Cutter",          "7340"),
    ("Engraver",              "7340"),
    ("Heat Press",            "7340"),
    ("Vinyl Cutter",          "7340"),
    ("Cable",                 "258"),
    ("USB Hub",               "74"),
    ("Network",               "342"),
    ("Storage",               "595"),
    ("Headphone",             "232"),
    ("Headset",               "232"),
    ("Speaker",               "232"),
    ("Keyboard",              "2168"),
    ("Mouse",                 "3387"),
    ("Monitor",               "397"),
    ("Camera",                "142"),
    ("Power Bank",            "5869"),
    ("Battery",               "5869"),
    ("UPS",                   "5869"),
    ("Sublimation",           "2872"),
    ("Art",                   "2872"),
    ("Craft",                 "2872"),
    ("DTF",                   "2872"),
    ("HTV",                   "2872"),
    ("Book",                  "783"),
    ("Pen",                   "932"),
    ("Pencil",                "932"),
    ("Marker",                "932"),
    ("Label",                 "5122"),
    ("Sticker",               "5122"),
    ("Envelope",              "1522"),
    ("Paper",                 "923"),
    ("File",                  "950"),
    ("Folder",                "950"),
    ("Laptop",                "328"),
    ("Computer",              "328"),
    ("Smart",                 "4745"),
    ("RC ",                   "1249"),
    ("Electronic Component",  "222"),
    ("Toy",                   "3805"),
    ("Packaging",             "5508"),
]

def get_category_code(categories: list, title: str = "") -> str:
    text = (" ".join(categories) + " " + title).lower()
    for keyword, code in CATEGORY_MAP:
        if keyword.lower() in text:
            return code
    return ""

# ── Ecwid API helpers ─────────────────────────────────────────────────────────
API_BASE = f"https://app.ecwid.com/api/v3/{STORE_ID}"

def api_get(endpoint: str, params: dict = None) -> dict:
    """GET request to Ecwid API; returns parsed JSON."""
    if not ECWID_TOKEN:
        raise RuntimeError(
            "ECWID_TOKEN environment variable is not set.\n"
            "  Local: export ECWID_TOKEN=secret_XXXX\n"
            "  GitHub Actions: add it as a repository secret named ECWID_TOKEN"
        )
    qs = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    url = f"{API_BASE}/{endpoint}" + (f"?{qs}" if qs else "")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {ECWID_TOKEN}"}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())

def fetch_all_products() -> list:
    """Page through Ecwid products endpoint and return every enabled product."""
    products = []
    offset   = 0
    limit    = 100
    while True:
        data = api_get("products", {"offset": offset, "limit": limit, "enabled": "true"})
        batch = data.get("items", [])
        products.extend(batch)
        total = data.get("total", 0)
        offset += limit
        print(f"  Fetched {len(products)}/{total} products...")
        if offset >= total:
            break
        time.sleep(0.3)   # be polite to the API
    return products

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_real_gtin(val: str) -> bool:
    return bool(re.fullmatch(r'\d{8,14}', (val or "").strip()))

def fmt_price(amount) -> str:
    """Format a numeric price as '1234.00 ZAR'."""
    try:
        return f"{float(amount):.2f} {CURRENCY}"
    except (TypeError, ValueError):
        return ""

def clean_description(text: str) -> str:
    """Strip markdown bold/italic, excessive whitespace, HTML tags."""
    text = re.sub(r'<[^>]+>', ' ', text or "")
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:5000]   # Google max description length

def availability_str(in_stock: bool, quantity) -> str:
    if in_stock:
        return "in stock"
    return "out of stock"

def indent_xml(elem, level=0):
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad

# ── Build Shopping Feed ───────────────────────────────────────────────────────
NS_G = "http://base.google.com/ns/1.0"

def build_shopping_feed(products: list) -> tuple:
    ET.register_namespace("g", NS_G)

    rss     = ET.Element("rss", {"version": "2.0",
                                  "xmlns:g": NS_G})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text       = f"{STORE_NAME} - Google Shopping Feed"
    ET.SubElement(channel, "link").text        = STORE_URL
    ET.SubElement(channel, "description").text = (
        f"Master Google Shopping feed for {STORE_NAME}. "
        f"Generated: {_now.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    added = skipped = sale_count = 0

    for p in products:
        product_id = str(p.get("id", ""))
        if not product_id:
            skipped += 1
            continue

        # ── Prices ──────────────────────────────────────────────────────────
        price         = p.get("price", 0)
        compare_price = p.get("compareToPrice")   # original / was-price
        on_sale       = compare_price and float(compare_price) > float(price)

        # Google expects:
        #   g:price         = the "was" / original price   (shown struck-through)
        #   g:sale_price    = the current selling price
        # If NOT on sale, g:price = current price, no g:sale_price
        g_price      = fmt_price(compare_price if on_sale else price)
        g_sale_price = fmt_price(price) if on_sale else None

        if not g_price:
            skipped += 1
            continue

        # ── Basic fields ─────────────────────────────────────────────────────
        title       = (p.get("name") or "").strip()
        description = clean_description(p.get("description") or p.get("name") or "")
        url         = p.get("url") or f"{STORE_URL}/products/{p.get('slug','')}"
        in_stock    = p.get("inStock", False)
        quantity    = p.get("quantity", 0)
        avail       = availability_str(in_stock, quantity)
        condition   = "new"   # adjust if you stock used/refurb items
        brand       = ""
        gtin_val    = ""

        # ── Attributes (Ecwid stores brand/GTIN here) ─────────────────────
        for attr in p.get("attributes", []):
            name = (attr.get("name") or "").lower()
            val  = (attr.get("value") or "").strip()
            if name in ("brand", "manufacturer"):
                brand = val
            elif name in ("gtin", "upc", "ean", "isbn", "mpn"):
                gtin_val = val

        # ── Images ──────────────────────────────────────────────────────────
        media     = p.get("media", {})
        images    = media.get("images", []) if media else []
        img_objs  = [i for i in images if i.get("isMain")]
        if not img_objs:
            img_objs = images
        image_url = ""
        extra_images = []
        if img_objs:
            def best_url(img):
                return (img.get("imageOriginalUrl") or
                        img.get("image800pxUrl") or
                        img.get("imageUrl") or "")
            image_url    = best_url(img_objs[0])
            extra_images = [best_url(i) for i in img_objs[1:5] if best_url(i)]

        # ── Categories ───────────────────────────────────────────────────────
        cats = [c.get("name", "") for c in p.get("categories", [])]
        google_cat = get_category_code(cats, title)

        # ── Weight ───────────────────────────────────────────────────────────
        weight_g = p.get("weight")   # grams in Ecwid
        weight_str = f"{weight_g:.1f} g" if weight_g else ""

        # ── Build <item> ─────────────────────────────────────────────────────
        item = ET.SubElement(channel, "item")

        def g_tag(tag, text):
            if text:
                ET.SubElement(item, f"{{{NS_G}}}{tag}").text = str(text)

        title_el = ET.SubElement(item, "title")
        title_el.text = title

        link_el = ET.SubElement(item, "link")
        link_el.text = url

        desc_el = ET.SubElement(item, "description")
        desc_el.text = description

        g_tag("id",           product_id)
        g_tag("condition",    condition)
        g_tag("availability", avail)
        g_tag("price",        g_price)

        if g_sale_price:
            g_tag("sale_price", g_sale_price)
            g_tag("sale_price_effective_date",
                  f"{_sale_start}/{SALE_END}")
            sale_count += 1

        if image_url:
            g_tag("image_link", image_url)
        for ei in extra_images:
            g_tag("additional_image_link", ei)

        if brand:
            g_tag("brand", brand)

        if is_real_gtin(gtin_val):
            g_tag("gtin", gtin_val)
        elif not brand:
            g_tag("identifier_exists", "no")

        if google_cat:
            g_tag("google_product_category", google_cat)

        # product_type from Ecwid categories
        if cats:
            g_tag("product_type", " > ".join(cats[:2]))

        if weight_str and weight_str not in ("0.0 g", "0 g"):
            g_tag("shipping_weight", weight_str)

        # MPN from Ecwid SKU (useful for Google)
        sku = p.get("sku") or p.get("vendorCode") or ""
        if sku:
            g_tag("mpn", sku)

        added += 1

    return rss, added, skipped, sale_count

# ── Build Local Inventory Feed ────────────────────────────────────────────────
def build_local_inventory_feed(products: list) -> tuple:
    """
    Google Local Inventory feed format.
    Required fields: id, store_code, availability, quantity, price
    """
    ET.register_namespace("g", NS_G)

    rss     = ET.Element("rss", {"version": "2.0", "xmlns:g": NS_G})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text       = f"{STORE_NAME} - Local Inventory Feed"
    ET.SubElement(channel, "link").text        = STORE_URL
    ET.SubElement(channel, "description").text = (
        f"Local inventory feed for {STORE_NAME}. "
        f"Generated: {_now.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    added = 0

    for p in products:
        product_id = str(p.get("id", ""))
        if not product_id:
            continue

        price         = p.get("price", 0)
        compare_price = p.get("compareToPrice")
        on_sale       = compare_price and float(compare_price) > float(price)

        g_price      = fmt_price(compare_price if on_sale else price)
        g_sale_price = fmt_price(price) if on_sale else None

        if not g_price:
            continue

        in_stock = p.get("inStock", False)
        quantity = p.get("quantity", 0)

        # For local inventory, use actual quantity if tracked, else assume in stock = available
        local_qty    = quantity if p.get("unlimited") is False else (1 if in_stock else 0)
        local_avail  = "in stock" if in_stock else "out of stock"

        item = ET.SubElement(channel, "item")

        def g_tag(tag, text):
            if text is not None and str(text) != "":
                ET.SubElement(item, f"{{{NS_G}}}{tag}").text = str(text)

        g_tag("id",              product_id)
        g_tag("store_code",      LOCAL_STORE["store_code"])
        g_tag("availability",    local_avail)
        g_tag("quantity",        local_qty)
        g_tag("price",           g_price)

        if g_sale_price:
            g_tag("sale_price", g_sale_price)
            g_tag("sale_price_effective_date",
                  f"{_sale_start}/{SALE_END}")

        g_tag("pickup_method",   LOCAL_STORE["pickup_method"])
        g_tag("pickup_sla",      LOCAL_STORE["pickup_sla"])

        added += 1

    return rss, added

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print(f"  Just Colours -- Master Feed Generator")
    print(f"  {_now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")

    if not ECWID_TOKEN:
        print("ERROR: ECWID_TOKEN is not set.")
        print("  Local:          export ECWID_TOKEN=secret_XXXX")
        print("  GitHub Actions: add ECWID_TOKEN as a repository secret")
        raise SystemExit(1)

    print("Step 1: Fetching all products from Ecwid API...")
    products = fetch_all_products()
    print(f"  Total products fetched: {len(products)}\n")

    print("Step 2: Building Google Shopping master feed...")
    shopping_rss, added, skipped, sale_count = build_shopping_feed(products)
    print(f"  Products added : {added}")
    print(f"  On sale        : {sale_count}")
    print(f"  Skipped        : {skipped}\n")

    print("Step 3: Building Local Inventory feed...")
    local_rss, local_added = build_local_inventory_feed(products)
    print(f"  Local inventory items: {local_added}\n")

    print(f"Step 4: Writing {OUTPUT_SHOPPING}...")
    indent_xml(shopping_rss)
    tree = ET.ElementTree(shopping_rss)
    with open(OUTPUT_SHOPPING, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="unicode", xml_declaration=False)
    print(f"  Done! {os.path.getsize(OUTPUT_SHOPPING) // 1024} KB")

    print(f"\nStep 5: Writing {OUTPUT_LOCAL_INV}...")
    indent_xml(local_rss)
    tree2 = ET.ElementTree(local_rss)
    with open(OUTPUT_LOCAL_INV, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree2.write(f, encoding="unicode", xml_declaration=False)
    print(f"  Done! {os.path.getsize(OUTPUT_LOCAL_INV) // 1024} KB")

    print("\n✅ Feed URLs (after commit to GitHub):")
    print(f"  Shopping:  https://raw.githubusercontent.com/7immyCPT/just-colours-google-feed/main/{OUTPUT_SHOPPING}")
    print(f"  Local Inv: https://raw.githubusercontent.com/7immyCPT/just-colours-google-feed/main/{OUTPUT_LOCAL_INV}")
    print()

if __name__ == "__main__":
    main()
