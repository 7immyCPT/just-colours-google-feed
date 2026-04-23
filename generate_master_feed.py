#!/usr/bin/env python3
"""Just Colours -- Google Shopping Master Feed Generator"""
import os, re, json, time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

# ── Config ──────────────────────────────────────────────────────────────
STORE_ID    = os.environ.get("STORE_CODE", "77567544")
TOKEN       = os.environ.get("ECWID_TOKEN", "")
STORE_NAME  = os.environ.get("STORE_NAME", "Just Colours")
STORE_URL   = "https://justcolours.co.za"
CURRENCY    = "ZAR"
TZ          = "+02:00"
NOW         = datetime.now(timezone.utc)
SALE_START  = NOW.strftime(f"%Y-%m-%dT00:00:00{TZ}")
SALE_END    = (os.environ.get("SALE_END_DATE") or
              (NOW + timedelta(days=30)).strftime(f"%Y-%m-%dT23:59:59{TZ}"))
# GBP_STORE_CODE must match your Google Business Profile store code exactly.
# It is NOT the same as the Ecwid store ID. Set it as a GitHub secret.
GBP_STORE_CODE = os.environ.get("GBP_STORE_CODE", "")
LOCAL_STORE   = {"store_code": GBP_STORE_CODE or STORE_ID, "pickup_method": "buy", "pickup_sla": "same day"}
SHIPPING_FREE_ABOVE = 1500   # ZAR — free shipping threshold
SHIPPING_RATE       = "99 ZAR"
OUT_SHOP      = "master_feed.xml"
OUT_LOCAL     = "local_inventory_feed.xml"
NS            = "http://base.google.com/ns/1.0"

ET.register_namespace("g", NS)

CATS = [
    ("FDM Printer","499682"),("Resin Printer","499682"),("3D Printer","499682"),
    ("3D Printing","499682"),("Filament","5074"),("3D Printer Suppli","5074"),
    ("3D Printer Accessor","5074"),("3D Pen","5074"),
    (" PLA ","5074"),(" ABS ","5074"),("PETG","5074"),("ASA ","5074"),("Resin","5074"),
    ("Printer","304"),("Scanner","304"),("Laminator","304"),("Shredder","304"),("Projector","304"),
    ("Ink","2314"),("Toner","2314"),("Cartridge","2314"),("Print Head","2314"),("Ribbon","2314"),
    ("Drum","2314"),("Remanufactur","2314"),("Canon GI","2314"),
    ("Laser Cutter","7340"),("Engraver","7340"),("Engraving","7340"),("Heat Press","7340"),
    ("Vinyl Cutter","7340"),("Cable","258"),("USB Hub","74"),("Network","342"),
    ("Storage","595"),("Headphone","232"),("Headset","232"),("Speaker","232"),
    ("Keyboard","2168"),("Mouse","3387"),("Monitor","397"),("Camera","142"),
    ("Power Bank","5869"),("Battery","5869"),("UPS","5869"),
    ("Sublimation","2872"),("Art","2872"),("Craft","2872"),("DTF","2872"),
    ("HTV","2872"),("Foil","2872"),
    ("Book","783"),("Pen","932"),("Pencil","932"),("Marker","932"),("Lead ","932"),
    ("Label","5122"),("Sticker","5122"),("Envelope","1522"),
    ("Paper","923"),("File","950"),("Folder","950"),
    ("Stationery","950"),("Stapler","950"),("Tape","950"),("Clip","950"),
    ("Punch","950"),("Staple","950"),("Eraser","950"),("Ruler","950"),
    ("Glue","950"),("Calculator","950"),
    ("Laptop","328"),("Computer","328"),("Smart","4745"),("RC ","1249"),
    ("Electronic Component","222"),("Toy","3805"),("Packaging","5508"),
    ("Fan","547"),
    ("Sensor","222"),("Stepper","222"),(" Motor","222"),("DuPont","258"),
    ("Nozzle","5074"),("Coupler","5074"),(" Spring","5074"),(" Screw","5074"),
    ("Quill","2872"),("Mat","2872"),("Vinyl","2872"),("Colour Code","5122"),
    ("Blade","7340"),
    ("Rubber Band","950"),("Board","923"),
    ("Screwdriver","3348"),("Calliper","3348"),("Drill Bit","3348"),
    ("LED","2184"),("Light Strip","2184"),("Neon","2184"),("Lamp","2184"),
    ("Duster","74"),("Screen Cleaner","74"),("Transducer","222"),
    ("Compatible","2314"),
    ("Heatflex","2872"),
]

def cat_code(cats, title=""):
    t = (" ".join(cats) + " " + title).lower()
    for k, c in CATS:
        if k.lower() in t: return c
    return ""

def pid(p):
    return (p.get("sku") or p.get("vendorCode") or "").strip() or str(p.get("id", ""))

def api(ep, params=None):
    if not TOKEN: raise RuntimeError("ECWID_TOKEN not set")
    qs = "&".join(f"{k}={v}" for k,v in (params or {}).items())
    url = f"https://app.ecwid.com/api/v3/{STORE_ID}/{ep}" + (f"?{qs}" if qs else "")
    req = Request(url, headers={"Accept":"application/json","Authorization":f"Bearer {TOKEN}"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def fetch():
    products, off, lim = [], 0, 100
    while True:
        d = api("products", {"offset":off,"limit":lim,"enabled":"true"})
        products.extend(d.get("items",[]))
        tot = d.get("total",0)
        print(f"  Fetched {len(products)}/{tot}")
        off += lim
        if off >= tot: break
        time.sleep(0.3)
    return products

def gtin_ok(v): return bool(re.fullmatch(r'\d{8,14}', (v or "").strip()))

def price(a):
    try:
        v = float(a)
        return f"{int(v)} {CURRENCY}" if v == int(v) else f"{v:.2f} {CURRENCY}"
    except: return ""

def clean(t):
    t = re.sub(r'<[^>]+>',' ', t or "")
    t = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', t)
    return re.sub(r'\s+',' ', t).strip()[:5000]

def g(parent, tag, val):
    if val is None or str(val) == "": return
    ET.SubElement(parent, f"{{{NS}}}{tag}").text = str(val)

def multi_g(parent, tag, vals):
    for val in vals:
        if val is None or str(val) == "": continue
        ET.SubElement(parent, f"{{{NS}}}{tag}").text = str(val)

def new_rss(title):
    rss = ET.Element("rss", {"version":"2.0"})
    ch  = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = title
    ET.SubElement(ch, "link").text  = STORE_URL
    ET.SubElement(ch, "description").text = f"Generated: {NOW.strftime('%Y-%m-%d %H:%M UTC')}"
    return rss, ch

def build_shopping(products):
    rss, ch = new_rss(f"{STORE_NAME} - Google Shopping Feed")
    added = skipped = sales = 0
    for p in products:
        item_id = pid(p)
        if not item_id: skipped += 1; continue
        prc   = p.get("price", 0)
        cp    = p.get("compareToPrice")
        on_sale = cp and float(cp) > float(prc)
        gp    = price(cp if on_sale else prc)
        gsp   = price(prc) if on_sale else None
        if not gp:
            print(f"  SKIP (no price): id={item_id} price={prc}")
            skipped += 1; continue

        sku   = (p.get("sku") or p.get("vendorCode") or "").strip()
        brand = gtin_val = ""
        for a in p.get("attributes",[]):
            n = (a.get("name") or "").lower(); v = (a.get("value") or "").strip()
            if n in ("brand","manufacturer"): brand = v
            elif n in ("gtin","upc","ean","isbn","mpn"): gtin_val = v

        media  = p.get("media") or {}
        imgs   = media.get("images",[])
        mains  = [i for i in imgs if i.get("isMain")] or imgs
        def bu(i): return i.get("imageOriginalUrl") or i.get("image800pxUrl") or i.get("imageUrl","")
        img0   = bu(mains[0]) if mains else ""
        extras = [bu(i) for i in mains[1:5] if bu(i)]

        cats   = [c.get("name","") for c in p.get("categories",[])]
        wt     = p.get("weight")
        wtstr  = f"{wt:.1f} g" if wt else ""

        item = ET.SubElement(ch, "item")
        multi_g(item, "included_destination", ["Shopping ads", "Free listings", "Local inventory ads", "Free local listings"])
        ET.SubElement(item, "title").text       = (p.get("name") or "").strip()
        ET.SubElement(item, "link").text        = p.get("url") or f"{STORE_URL}/products/{p.get('slug','')}"
        ET.SubElement(item, "description").text = clean(p.get("description") or p.get("name",""))

        g(item, "id",           item_id)
        g(item, "condition",    "new")
        g(item, "availability", "in stock" if p.get("inStock") else "out of stock")
        g(item, "price",        gp)
        if gsp:
            g(item, "sale_price", gsp)
            g(item, "sale_price_effective_date", f"{SALE_START}/{SALE_END}")
            sales += 1
        if img0: g(item, "image_link", img0)
        for e in extras: g(item, "additional_image_link", e)
        if brand: g(item, "brand", brand)
        if gtin_ok(gtin_val): g(item, "gtin", gtin_val)
        elif not brand and not sku: g(item, "identifier_exists", "no")
        gc = cat_code(cats, p.get("name",""))
        if gc: g(item, "google_product_category", gc)
        if cats: g(item, "product_type", " > ".join(cats[:2]))
        if wtstr and wtstr not in ("0.0 g","0 g"): g(item, "shipping_weight", wtstr)
        if sku: g(item, "mpn", sku)
        ship_price = "0 ZAR" if float(prc) >= SHIPPING_FREE_ABOVE else SHIPPING_RATE
        ship = ET.SubElement(item, f"{{{NS}}}shipping")
        ET.SubElement(ship, f"{{{NS}}}country").text = "ZA"
        ET.SubElement(ship, f"{{{NS}}}price").text   = ship_price
        added += 1
    return rss, added, skipped, sales

def build_local(products):
    rss, ch = new_rss(f"{STORE_NAME} - Local Inventory Feed")
    added = 0
    for p in products:
        item_id = pid(p)
        if not item_id: continue
        prc   = p.get("price", 0)
        cp    = p.get("compareToPrice")
        on_sale = cp and float(cp) > float(prc)
        gp    = price(cp if on_sale else prc)
        gsp   = price(prc) if on_sale else None
        if not gp: continue
        in_s  = p.get("inStock", False)
        qty   = p.get("quantity", 0)
        lqty  = qty if p.get("unlimited") is False else (9999 if in_s else 0)
        item  = ET.SubElement(ch, "item")
        g(item, "id",              item_id)
        g(item, "store_code",      LOCAL_STORE["store_code"])
        g(item, "availability",    "in stock" if in_s else "out of stock")
        g(item, "quantity",        lqty)
        g(item, "price",           gp)
        if gsp:
            g(item, "sale_price", gsp)
            g(item, "sale_price_effective_date", f"{SALE_START}/{SALE_END}")
        g(item, "pickup_method",   LOCAL_STORE["pickup_method"])
        g(item, "pickup_sla",      LOCAL_STORE["pickup_sla"])
        added += 1
    return rss, added

def write(rss, path):
    tree = ET.ElementTree(rss)
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<?xml-stylesheet type="text/xsl" href="feed.xsl"?>\n')
        tree.write(f, encoding="unicode", xml_declaration=False)

def main():
    print(f"\n{'='*60}\n  {STORE_NAME} -- Master Feed Generator\n  {NOW.strftime('%Y-%m-%d %H:%M UTC')}\n{'='*60}\n")
    if not TOKEN: print("ERROR: ECWID_TOKEN not set"); raise SystemExit(1)
    if not GBP_STORE_CODE:
        print("WARNING: GBP_STORE_CODE not set — local inventory feed will use Ecwid store ID as store_code.")
        print("         Google will deny ALL local items unless this matches your Google Business Profile store code.")
        print("         Add GBP_STORE_CODE as a GitHub secret and set it in the workflow env block.\n")
    print("Fetching products...")
    products = fetch()
    print(f"Total: {len(products)}\n")
    print("Building shopping feed...")
    rss, added, skipped, sales = build_shopping(products)
    print(f"Added:{added} Sales:{sales} Skipped:{skipped}")
    print("Building local inventory feed...")
    lrss, ladded = build_local(products)
    print(f"Local:{ladded}")
    write(rss,  OUT_SHOP);  print(f"Wrote {OUT_SHOP}  ({os.path.getsize(OUT_SHOP)//1024}KB)")
    write(lrss, OUT_LOCAL); print(f"Wrote {OUT_LOCAL} ({os.path.getsize(OUT_LOCAL)//1024}KB)")
    print(f"\n✓ Done!")

if __name__ == "__main__":
    main()
