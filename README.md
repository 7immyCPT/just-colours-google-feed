# just-colours-google-feed

Automated Google Merchant Center feed generator for [Just Colours](https://justcolours.co.za).

Pulls live product data directly from the **Ecwid API** (including sale prices and compare-to prices) and generates two XML feeds every 6 hours via GitHub Actions.

---

## Feeds

| Feed | File | Purpose |
|---|---|---|
| Google Shopping (primary) | `master_feed.xml` | Submit to GMC as your **main** feed |
| Local Inventory | `local_inventory_feed.xml` | Submit to GMC as a **local inventory** feed |

**Feed URLs** (use these in Google Merchant Center → scheduled fetch):
```
https://raw.githubusercontent.com/7immyCPT/just-colours-google-feed/main/master_feed.xml
https://raw.githubusercontent.com/7immyCPT/just-colours-google-feed/main/local_inventory_feed.xml
```

---

## What the master feed includes

| Google attribute | Source |
|---|---|
| `g:id` | Ecwid product ID |
| `title` | Product name |
| `description` | Product description (markdown stripped) |
| `link` | Product page URL |
| `g:image_link` + `g:additional_image_link` | All product images |
| `g:price` | **Compare-to (original) price** when on sale; otherwise current price |
| `g:sale_price` | **Current price** — only present when product is on sale |
| `g:sale_price_effective_date` | Auto-set: today → SALE_END_DATE |
| `g:availability` | in stock / out of stock |
| `g:condition` | new |
| `g:brand` | From Ecwid product attributes |
| `g:gtin` | From Ecwid product attributes |
| `g:mpn` | Ecwid SKU |
| `g:google_product_category` | Mapped from Ecwid categories |
| `g:product_type` | Ecwid category path |
| `g:shipping_weight` | From Ecwid weight field |
| `g:identifier_exists` | `no` — only when no brand AND no GTIN |

---

## Security — keeping your API key private

The Ecwid API token is stored as a **GitHub Secret** and is never written into any file in this repo.

### How to add your secret

1. Go to your repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `ECWID_TOKEN`
4. Value: your Ecwid private token (from Ecwid admin → Apps → API)
5. Click **Add secret**

That's it. The workflow injects it at runtime as an environment variable. It is never visible in logs.

---

## How to set a custom sale end date

**Via GitHub Actions UI (one-off):**
1. Go to **Actions → Generate Google Feeds → Run workflow**
2. Enter a date like `2026-05-31T23:59+02:00`
3. Click **Run workflow**

**Permanently (for a long-running sale):**
Edit `.github/workflows/generate_feeds.yml` and set `SALE_END_DATE` directly under the `env:` block.

---

## Local development

```bash
git clone https://github.com/7immyCPT/just-colours-google-feed
cd just-colours-google-feed
export ECWID_TOKEN=secret_XXXX          # your real token — never commit this
python3 generate_master_feed.py
```

Output files (`master_feed.xml`, `local_inventory_feed.xml`) are gitignored locally but committed by the Actions bot.

---

## Files

```
.github/workflows/generate_feeds.yml   GitHub Actions schedule + secret injection
generate_master_feed.py                 Feed generator (no API key in code)
master_feed.xml                         Generated — do not edit manually
local_inventory_feed.xml                Generated — do not edit manually
README.md
```

> **Note:** `generate_supplemental_feed.py` and `supplemental_feed.xml` are kept for reference
> but are no longer needed once you switch GMC to use `master_feed.xml` as your primary feed.
