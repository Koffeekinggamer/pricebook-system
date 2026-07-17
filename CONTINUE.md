# FAF Pricebook — LIVE

**Updated:** 2026-07-17  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/faf-pricebook-system  
**Status:** LIVE + standardized · **~29,638 rows · 13 vendors**  
Smoke-test quote PDF: `smoke_test_quote.pdf` · Windy woods mapped · Millers descriptions filled

## Run (production)

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py
```

Open **http://localhost:8501**

CLI smoke:

```bash
.venv/bin/python -m backend.cli stats
.venv/bin/python -m backend.cli search "nightstand" --vendor "Genuine Oak"
.venv/bin/python -m backend.cli vendors
```

## Vendors

| Vendor | Rows | Mult | Notes |
|--------|------|------|-------|
| Hope Wood | 14,931 | 2.7 | 5 woods × unfinished/finished |
| Genuine Oak | 5,613 | **1.7** | woods slash-normalized; Master dups collapsed |
| FN Chair | 3,067 | 2.7 | item name = SKU; wood groups canonical |
| Windy Acres Furniture | ~1,501 | 2.7 | Real wood groups + finished/unfinished |
| Millers Woodshop | 1,225 | 2.7 | Descriptions = section + SKU |
| Premier Woodcraft | 1,016 | 2.7 | 2 wood tiers, wholesale base |
| Rainbow Bedding | 708 | 2.7 | Jan wholesale; size options clean |
| LuxHome | 558 | 2.7 | Standard/Premium/Ultra/Genuine |
| Patio Kraft | 452 | 2.7 | Standard/Bright/Woodgrain colors |
| Charleston Forge | 248 | 2.7 | junk cols removed |
| Beaverdam | 143 | 2.7 | flat SKU+price |
| GVWI | 93 | 2.7 | flat SKU+price |
| LAMB | 83 | 2.7 | wood groups canonical |

## Decisions locked in

- **One builder = one vendor** — never duplicate (MWS + Millers → Millers Woodshop only).
- Default import mode: **replace_vendor** (wipe that builder, load new book).
- **Rainbow Bedding** = Jan 2026 wholesale file (not the pre-marked Rainbow export).
- **AJ’s LuxHome addon** = same builder as LuxHome → not a second vendor.
- **Genuine Oak** stays **1.7×** per builder Markup sheet.
- **Local DB** gitignored (never on GitHub).

## Next prompt (copy-paste)

```
Continue FAF Pricebook at ~/FAF-pricebook.

## Context (do not re-litigate)
- Streamlit + SQLite private multiplier engine for Foothills Amish Furniture
- Repo (code): https://github.com/Koffeekinggamer/faf-pricebook-system (main, in sync)
- Local only: master_pricebook.db (~29,749 rows · 13 vendors) — gitignored
- UI: pricebook_app.py · logic: backend.PriceBookService
- Standards: STANDARDS.md · layout: LAYOUT_SYSTEM.md · status: CONTINUE.md
- Default mult 2.7; Genuine Oak 1.7; base = wholesale; retail = base × mult
- One builder = one vendor (replace_vendor default; never duplicate builders)
- Imports auto-standardize via backend.standardize

## Builders loaded (one each)
Hope Wood, Genuine Oak, FN Chair, Windy Acres Furniture, Millers Woodshop,
Premier Woodcraft, Rainbow Bedding, LuxHome, Patio Kraft, Charleston Forge,
Beaverdam, GVWI, LAMB

## Run
cd ~/FAF-pricebook && source .venv/bin/activate && streamlit run pricebook_app.py
# http://localhost:8501

## Next work (pick highest value / do in order unless I say otherwise)
1) Floor smoke-test with me: search + quote PDF for real SKUs I name
2) Improve Windy Acres Wood Tier 1–4 labels if we can map real wood names from the source file
3) Improve Millers descriptions (many description = part_number only)
4) Collection cleanup: fewer null collections; drop junk section titles
5) Optional: private backup path for master_pricebook.db (not GitHub)

Rules: prefer backend over stuffing Streamlit; replace_vendor on re-import;
keep long-form rows; push code to GitHub when done; never commit *.db.

Next: [tell me what you want — or say “keep going” and start with #1–3]
```
