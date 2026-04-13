#!/usr/bin/env python3
"""
Just Colours -- Google Shopping Supplemental Feed Generator
Fetches the live Ecwid primary XML feed and builds a Google-compliant
supplemental feed. No CSV needed -- fully self-contained.
Run: python3 generate_supplemental_feed.py
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen
import os

PRIMARY_FEED_URL = "https://d2hku29108hzuu.cloudfront.net/product_feed/77567544/google_shopping/bapCC3RJp2vFqmkt.xml"
OUTPUT_FILE      = "supplemental_feed.xml"
STORE_NAME       = "Just Colours"
STORE_URL        = "https://justcolours.co.za"
FEED_CURRENCY    = "ZAR"
STORE_CODE       = "77567544"

CATEGORY_MAP = [
    ("FDM Printers",           "499682"),
    ("Resin Printers",         "499682"),
    ("3D Printers",            "499682"),
    ("3D Printing",            "499682"),
    ("Filament",               "5074"),
    ("3D Printer Supplies",    "5074"),
    ("3D Printer Accessories", "5074"),
    ("3D Pens",                "5074"),
    ("Resin",                  "5074"),
    ("Printers, Scanners",     "304"),
    ("Printers",               "304"),
    ("Scanners",               "304"),
    ("Ink",                    "2314"),
    ("Toner",                  "2314"),
    ("Cartridge",              "2314"),
    ("Print Head",             "2314"),
    ("Ribbon",                 "2314"),
    ("Laser Cutter",           "7340"),
    ("Engraver",               "7340"),
    ("Heat Press",             "7340"),
    ("Vinyl Cutter",           "7340"),
    ("Cable",                  "258"),
    ("USB Hub",                "74"),
    ("Network",                "342"),
    ("Storage",                "595"),
    ("Headphone",              "232"),
    ("Headset",                "232"),
    ("Speaker",                "232"),
    ("Keyboard",               "2168"),
    ("Mouse",                  "3387"),
    ("Monitor",                "397"),
    ("Camera",                 "142"),
    ("Power Bank",             "5869"),
    ("Battery",                "5869"),
    ("UPS",                    "5869"),
    ("Sublimation",            "2872"),
    ("Art",                    "2872"),
    ("Craft",                  "2872"),
    ("DTF",                    "2872"),
    ("HTV",                    "2872"),
    ("Book",                   "783"),
    ("Pen",                    "932"),
    ("Pencil",                 "932"),
    ("Marker",                 "932"),
    ("Label",                  "5122"),
    ("Sticker",                "5122"),
    ("Envelope",               "1522"),
    ("Paper",                  "923"),
    ("File",                   "950"),
    ("Folder",                 "950"),
    ("Laptop",                 "328"),
    ("Computer",               "328"),
    ("Smart",                  "4745"),
    ("RC",                     "1249"),
    ("Electronic Component",   "222"),
    ("Toy",                    "3805"),
    ("Packaging",              "5508"),
]

def get_category_code(product_type, title=""):
    text = (product_type + " " + title).lower()
    for keyword, code in CATEGORY_MAP:
        if keyword.lower() in text:
            return code
    return ""

def is_real_gtin(val):
    return bool(re.fullmatch(r'\d{8,14}', (val or "").strip()))

def fetch_primary_feed():
    print(f"  Fetching: {PRIMARY_FEED_URL}")
    with urlopen(PRIMARY_FEED_URL, timeout=60) as r:
        raw = r.read()
    print(f"  Downloaded {len(raw)//1024} KB")
    return ET.fromstring(raw)

def build_supplemental_feed(primary_root):
    ns_g = "http://base.google.com/ns/1.0"
    ET.register_namespace('g', ns_g)
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = f"{STORE_NAME} -- Supplemental Feed"
    ET.SubElement(channel, 'link').text  = STORE_URL
    ET.SubElement(channel, 'description').text = (
        "Supplemental Google Shopping feed. "
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    items = primary_root.findall('.//item')
    added = skipped = 0

    for src in items:
        def g(tag):
            el = src.find(f'{{{ns_g}}}{tag}')
            return (el.text or "").strip() if el is not None else ""

        product_id   = g('id')
        availability = g('availability')
        price        = g('price')
        brand        = g('brand')
        gtin         = g('gtin')
        condition    = g('condition') or 'new'
        product_type = g('product_type')
        title_el     = src.find('title')
        title        = (title_el.text or "") if title_el is not None else ""
        weight       = g('shipping_weight')

        if not product_id:
            skipped += 1
            continue

        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, f'{{{ns_g}}}store_code').text   = STORE_CODE
        ET.SubElement(item, f'{{{ns_g}}}id').text           = product_id
        ET.SubElement(item, f'{{{ns_g}}}availability').text = availability or 'in_stock'
        ET.SubElement(item, f'{{{ns_g}}}condition').text    = condition
        if price:
            ET.SubElement(item, f'{{{ns_g}}}price').text = price
        if brand:
            ET.SubElement(item, f'{{{ns_g}}}brand').text = brand
        if is_real_gtin(gtin):
            ET.SubElement(item, f'{{{ns_g}}}gtin').text = gtin
        elif not brand:
            ET.SubElement(item, f'{{{ns_g}}}identifier_exists').text = 'no'
        cat_code = get_category_code(product_type, title)
        if cat_code:
            ET.SubElement(item, f'{{{ns_g}}}google_product_category').text = cat_code
        if weight and weight not in ('0.0 g', '0 g', ''):
            ET.SubElement(item, f'{{{ns_g}}}shipping_weight').text = weight
        added += 1

    return rss, added, skipped

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

def main():
    print("\n" + "="*60)
    print("  Just Colours -- Supplemental Feed Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    print("Step 1: Fetching primary feed...")
    primary_root = fetch_primary_feed()
    print()
    print("Step 2: Building supplemental feed...")
    rss, added, skipped = build_supplemental_feed(primary_root)
    print(f"  Added  : {added}")
    print(f"  Skipped: {skipped}")
    print()
    print(f"Step 3: Writing {OUTPUT_FILE}...")
    indent_xml(rss)
    tree = ET.ElementTree(rss)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='unicode', xml_declaration=False)
    print(f"  Done! {os.path.getsize(OUTPUT_FILE)//1024} KB")
    print("\nFeed URL:")
    print("  https://raw.githubusercontent.com/7immyCPT/just-colours-google-feed/main/supplemental_feed.xml\n")

if __name__ == '__main__':
    main()
