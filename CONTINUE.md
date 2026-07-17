# FAF Pricebook — LIVE

**Updated:** 2026-07-17  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/faf-pricebook-system  
**Status:** Master data cleaned · app ready · **~41,200 rows · 13 vendors**

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
| Hope Wood | 14,933 | 2.7 | unfinished + finished × 5 woods |
| Genuine Oak | 9,095 | **1.7** | workbook Markup sheet |
| Millers Woodshop | 5,852 | 2.7 | 2026 only (MWS 2023 removed) |
| Windy Acres Furniture | 3,504 | 2.7 | |
| FN Chair | 3,067 | 2.7 | PL To Export; item name = SKU |
| Rainbow Bedding | 1,540 | 2.7 | **Jan 2026 wholesale** bases |
| Premier Woodcraft | 1,028 | 2.7 | wholesale under markup formulas |
| Charleston Forge | 849 | 2.7 | |
| LuxHome | 558 | 2.7 | fabric grades; AJ addon = identical skip |
| Patio Kraft | 452 | 2.7 | color tiers Standard/Bright/Woodgrain |
| Beaverdam | 143 | 2.7 | |
| GVWI | 93 | 2.7 | |
| LAMB | 86 | 2.7 | |

## Decisions locked in

- **Rainbow Bedding** = Jan 2026 wholesale file (not the pre-marked Rainbow export).
- **AJ’s LuxHome addon** = 100% same as wholesale book → not double-loaded.
- **Genuine Oak** stays **1.7×** per builder Markup sheet.
- **Local DB** gitignored (never on GitHub).

## Resume prompt

```
Continue FAF Pricebook at ~/FAF-pricebook — live system.
Next: [your ask].
```
