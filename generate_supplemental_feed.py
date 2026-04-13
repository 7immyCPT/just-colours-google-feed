#!/usr/bin/env python3
"""
Just Colours — Google Shopping Supplemental Feed Generator
===========================================================
Fetches the live Ecwid primary feed XML, then builds a Google-compliant
supplemental feed XML that adds the missing fields Google requires:

  Required supplemental fields added:
  - g:id              (matched to primary feed)
  - g:availability    (in stock / out of stock / preorder)
  - g:price           (with ZAR currency)
  - g:shipping_weight (from Ecwid data where available)
  - g:gtin            (real numeric GTINs only)
  - g:brand           (brand name)
  - g:condition       (new)
  - g:google_product_category (corrected category codes)

Run manually:
  python3 generate_supplemental_feed.py

Run on a schedule (cron every 6 hours):
  0 */6 * * * /usr/bin/python3 /path/to/generate_supplemental_feed.py

The output XML is saved to: supplemental_feed.xml
To serve it automatically, host this file on any static file server or
upload to Google Cloud Storage / AWS S3 and register the URL in
Merchant Center > Data Sources > Add supplemental source.
"""

import csv
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from io import StringIO
import urllib.request
import os

# ── Config ──────────────────────────────────────────────────────────────────
ECWID_CSV_URL   = None   # Set to None to use local CSV file
LOCAL_CSV_PATH  = "catalog_2026-04-12_21-10.csv"   # fallback local CSV
OUTPUT_FILE     = "supplemental_feed.xml"
STORE_NAME      = "Just Colours"
STORE_URL       = "https://justcolours.co.za"
FEED_CURRENCY   = "ZAR"
STORE_CODE      = "77567544"   # Google Merchant Center store code

# ── Google Product Category Map ─────────────────────────────────────────────
CATEGORY_MAP = [
    ("3D Printing / FDM Printers",        "499682"),
    ("3D Printing / Resin Printers",      "499682"),
    ("3D Printing / Resin",               "5074"),
    ("3D Printing / Filament",            "5074"),
    ("3D Printing / Spares",              "499682"),
    ("3D Printing / Accessories",         "5074"),
    ("3D Printing / 3D Pens",            "5074"),
    ("3D Printing",                       "499682"),
    ("Printers, Scanners",                "304"),
    ("Ink & Toners",                      "2314"),
    ("Laser Cutters & Engravers",         "7340"),
    ("Accessories / Adapters & Cables",   "258"),
    ("Accessories / USB Hubs",            "74"),
    ("Accessories / Bags",                "5577"),
    ("Accessories / Cameras",            "142"),
    ("Accessories / Network",            "342"),
    ("Accessories / Portable Power",     "5869"),
    ("Accessories / Storage Devices",    "595"),
    ("Accessories / Peripherals / Head", "232"),
    ("Accessories / Peripherals / Key",  "2168"),
    ("Accessories / Peripherals / Mon",  "397"),
    ("Accessories / Peripherals / Mouse Pads", "3387"),
    ("Accessories / Peripherals",        "74"),
    ("Accessories / Miscellaneous",      "74"),
    ("Accessories",                      "74"),
    ("Smart Devices & Tech",             "4745"),
    ("RC & Electronic Components / RC",  "1249"),
    ("RC & Electronic Components",      "222"),
    ("Art & Crafts / Equipment / Heat",  "7340"),
    ("Art & Crafts / Equipment / Sub",   "304"),
    ("Art & Crafts / Equipment / Vinyl", "7340"),
    ("Art & Crafts / Equipment",         "7340"),
    ("Art & Crafts",                     "2872"),
    ("Stationery / Books",               "783"),
    ("Stationery / Pens",               "932"),
    ("Stationery / Paper & Media / Stickers", "5122"),
    ("Stationery / Paper & Media / Envelopes", "1522"),
    ("Stationery / Paper & Media / Files", "950"),
    ("Stationery / Paper & Media",       "923"),
    ("Stationery",                       "4181"),
    ("Computer's and Laptop's",          "328"),
    ("Technical & Educational Toys",     "3805"),
    ("Packaging",                        "5508"),
    ("Print/Copy/Email/Scan",            "304"),
    ("Printer Repair",                   "304"),
    ("Kolok Consignment",               "2314"),
    ("Support Local",                    "4181"),
]

def get_category_code(cat1):
    cat1 = (cat1 or "").strip()
    for prefix, code in CATEGORY_MAP:
        if cat1.startswith(prefix):
            return code
    return ""

def is_real_gtin(val):
    """True if value looks like a real numeric EAN/UPC barcode (8-14 digits)."""
    return bool(re.fullmatch(r'\d{8,14}', (val or "").strip()))

def clean_gtin(upc, sku):
    """Return only the real numeric GTIN, stripping SKU duplicates."""
    if not upc:
        return ""
    parts = [p.strip() for p in str(upc).split('|') if p.strip()]
    real = [p for p in parts if is_real_gtin(p) and p != sku]
    return real[0] if real else ""

def map_availability(row):
    """Map Ecwid availability fields to Google availability values."""
    qty      = int(row.get('product_quantity') or 0)
    avail    = row.get('product_is_available', 'false').lower()
    tracked  = row.get('product_is_inventory_tracked', 'false').lower()
    oos_behaviour = row.get('product_quantity_out_of_stock_behaviour', '')

    if avail != 'true':
        return 'out_of_stock'
    if tracked == 'true':
        if qty > 0:
            return 'in_stock'
        elif oos_behaviour == 'PREORDER':
            return 'preorder'
        else:
            return 'out_of_stock'
    return 'in_stock'  # not tracked = assume in stock

def load_products():
    """Load products from local CSV file."""
    print(f"  Loading from local CSV: {LOCAL_CSV_PATH}")
    with open(LOCAL_CSV_PATH, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [r for r in reader if r.get('type') == 'product']

def build_supplemental_feed(products):
    """Build Google supplemental feed XML from product list."""

    # RSS root — register namespace first to avoid duplicate xmlns attributes
    ET.register_namespace('g', 'http://base.google.com/ns/1.0')
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')

    ET.SubElement(channel, 'title').text = f"{STORE_NAME} — Supplemental Feed"
    ET.SubElement(channel, 'link').text  = STORE_URL
    ET.SubElement(channel, 'description').text = (
        f"Supplemental Google Shopping feed for {STORE_NAME}. "
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    added = 0
    skipped = 0

    for row in products:
        sku   = (row.get('product_sku') or '').strip()
        name  = (row.get('product_name') or '').strip()
        price = (row.get('product_price') or '').strip()
        brand = (row.get('product_brand') or '').strip()
        upc   = (row.get('product_upc') or '').strip()
        cat1  = (row.get('product_category_1') or '').strip()
        weight = (row.get('product_weight') or '').strip()

        # Skip products with no SKU — can't match to primary feed
        if not sku:
            skipped += 1
            continue

        # Skip internal/write-off categories
        skip_cats = ['Stock Write Off', "Don't Sell On Web", 'Courier',
                     'Printer Repair', 'Kolok Consignment', 'Clearance stock']
        if any(cat1.startswith(c) for c in skip_cats):
            skipped += 1
            continue

        item = ET.SubElement(channel, 'item')

        g = 'http://base.google.com/ns/1.0'

        # ── Required fields ──────────────────────────────────────────────
        ET.SubElement(item, f'{{{g}}}store_code').text       = STORE_CODE
        ET.SubElement(item, f'{{{g}}}id').text               = sku
        ET.SubElement(item, f'{{{g}}}availability').text = map_availability(row)
        ET.SubElement(item, f'{{{g}}}condition').text    = 'new'

        if price:
            ET.SubElement(item, f'{{{g}}}price').text = f"{float(price):.2f} {FEED_CURRENCY}"

        # ── Optional but strongly recommended ────────────────────────────
        if brand:
            ET.SubElement(item, f'{{{g}}}brand').text = brand

        gtin = clean_gtin(upc, sku)
        if gtin:
            ET.SubElement(item, f'{{{g}}}gtin').text = gtin
        elif not brand:
            # Tell Google explicitly there's no identifier
            ET.SubElement(item, f'{{{g}}}identifier_exists').text = 'no'

        # Google product category (corrected)
        cat_code = row.get('product_google_product_category_code', '').strip()
        if not cat_code:
            cat_code = get_category_code(cat1)
        if cat_code:
            ET.SubElement(item, f'{{{g}}}google_product_category').text = cat_code

        # Shipping weight (convert from kg/g to g for Google)
        if weight and weight not in ('', '0', '0.0'):
            try:
                w_val = float(weight)
                # Ecwid stores weight in kg, Google wants value + unit
                ET.SubElement(item, f'{{{g}}}shipping_weight').text = f"{w_val:.3f} kg"
            except ValueError:
                pass

        added += 1

    return rss, added, skipped

def indent_xml(elem, level=0):
    """Add pretty-print indentation to XML."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent

def main():
    print(f"\n{'='*60}")
    print(f"  Just Colours — Supplemental Feed Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print("Step 1: Loading product data...")
    products = load_products()
    print(f"  Loaded {len(products)} products\n")

    print("Step 2: Building supplemental feed XML...")
    rss, added, skipped = build_supplemental_feed(products)
    print(f"  Added  : {added} products")
    print(f"  Skipped: {skipped} products\n")

    print(f"Step 3: Writing output to {OUTPUT_FILE}...")
    indent_xml(rss)
    tree = ET.ElementTree(rss)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='unicode', xml_declaration=False)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"  Done! File size: {size_kb:.1f} KB\n")
    print(f"{'='*60}")
    print(f"  Next steps:")
    print(f"  1. Host {OUTPUT_FILE} on a public URL")
    print(f"  2. In Merchant Center > Data Sources > Add source")
    print(f"     > Supplemental source > File (URL)")
    print(f"  3. Set fetch schedule to every 6 hours")
    print(f"  4. Schedule this script with cron:")
    print(f"     0 */6 * * * python3 /path/to/generate_supplemental_feed.py")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
