# FAF Pricebook — LIVE

**Updated:** 2026-07-17  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/faf-pricebook-system  
**Status:** LIVE + **standardized** · **~29,749 clean rows · 13 vendors**  
(Junk matrix columns removed; all vendors share one field shape — see **STANDARDS.md**)

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
| Windy Acres Furniture | 1,612 | 2.7 | FINISHED cols → Wood Tier N |
| Millers Woodshop | 1,225 | 2.7 | junk `col_*` matrix cols removed |
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

## Resume prompt

```
Continue FAF Pricebook at ~/FAF-pricebook — live system.
Next: [your ask].
```
