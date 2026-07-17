# FAF Pricebook — LIVE

**Updated:** 2026-07-17  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/pricebook-system  
**Status:** LIVE · floor UI polish · search + quotes + vendors · **~29,631 rows · 13 vendors**

## Run

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py
# http://localhost:8501
```

## Backup (local only — never GitHub)

```bash
.venv/bin/python -m backend.cli backup-db
# → ~/Documents/FAF-pricebook-backups/master_pricebook-YYYYMMDD-HHMMSS.db
# keeps newest 20 copies
```

Or: `./scripts/backup_db.sh` · override dir with `FAF_PRICEBOOK_BACKUP_DIR=...`

## CLI

```bash
.venv/bin/python -m backend.cli stats
.venv/bin/python -m backend.cli vendors
.venv/bin/python -m backend.cli search "nightstand" --vendor "Genuine Oak"
.venv/bin/python -m backend.cli standardize
.venv/bin/python -m backend.cli backup-db
```

## Vendors (one each)

| Vendor | Rows | Mult | Collections notes |
|--------|------|------|-------------------|
| Hope Wood | 14,931 | 2.7 | Real categories (Sofa Mate, Queen Anne, Mission, …) |
| Genuine Oak | 5,613 | **1.7** | default **Casegoods** + named collections |
| FN Chair | 3,067 | 2.7 | default **Seating** |
| Windy Acres Furniture | 1,501 | 2.7 | Real wood groups + fin/unf |
| Millers Woodshop | 1,225 | 2.7 | Mult-* → Gun Cabinets / Bookcases / TV Consoles |
| Premier Woodcraft | 1,016 | 2.7 | |
| Rainbow Bedding | 708 | 2.7 | footer summary junk removed |
| LuxHome | 558 | 2.7 | |
| Patio Kraft | 452 | 2.7 | |
| Charleston Forge | 244 | 2.7 | |
| Beaverdam | 143 | 2.7 | |
| GVWI | 93 | 2.7 | |
| LAMB | 80 | 2.7 | |

## Decisions locked in

- One builder = one vendor (`replace_vendor` default)
- Collections: drop option/upcharge junk; keep product categories
- Genuine Oak mult **1.7**; others **2.7**
- Local DB gitignored; backup to Documents only
- Search ranks exact SKU first, finished woods next; demotes dust covers (`VECG` before `VECG-DC`)

## When UI-ready?

**Backend is ready for UI-focused work now.**  
Master data, one-builder policy, search ranking, quotes, import/batch, mults, backup, and standards are solid. Remaining backend polish (more builders, data fixes) can happen in parallel with UI.

## Next prompt (copy-paste)

```
Continue FAF Pricebook at ~/FAF-pricebook.

## Context (do not re-litigate)
- Streamlit + SQLite private multiplier engine — Foothills Amish Furniture
- Repo: https://github.com/Koffeekinggamer/pricebook-system (origin/main)
- Also exists (older twin): faf-pricebook-system — do NOT use; origin is pricebook-system
- Folder: ~/FAF-pricebook · work here (or Documents/GitHub/pricebook-system)
- Local DB only: master_pricebook.db (~29,631 rows · 13 vendors · 265 collections) — gitignored
- UI: pricebook_app.py (thin) · logic: backend.PriceBookService
- Docs: STANDARDS.md · LAYOUT_SYSTEM.md · CONTINUE.md · PROMPTS.md
- Mult: default 2.7; Genuine Oak 1.7; wholesale base × mult = retail
- One builder = one vendor; replace_vendor default; never duplicate builders
- Search ranks exact SKU first, finished next, dust covers demoted
- Backup: python -m backend.cli backup-db → ~/Documents/FAF-pricebook-backups/

## Builders (one each)
Hope Wood, Genuine Oak, FN Chair, Windy Acres Furniture, Millers Woodshop,
Premier Woodcraft, Rainbow Bedding, LuxHome, Patio Kraft, Charleston Forge,
Beaverdam, GVWI, LAMB

## Run
cd ~/FAF-pricebook && source .venv/bin/activate && streamlit run pricebook_app.py
# http://localhost:8501

## Phase status
DONE: importers, standardize, collections, one-builder policy, floor search
ranking, quote PDF smoke test, private DB backup, GitHub sync to pricebook-system.
BACKEND IS READY FOR UI WORK.

## Next work — UI-first (default if I say “keep going”)
1) Floor UI polish (Search tab): bigger search box, finished-only default,
   clearer retail emphasis, keyboard-friendly add-to-quote
2) Quotes tab polish: edit qty/discount inline, better PDF layout with FAF branding,
   line remove without expander friction
3) Vendors tab: simple mult edit + row counts; hide raw tech noise
4) Home/dashboard strip: today’s quote count, last backup hint, top vendors
5) Optional later backend: more builders, Rainbow null collections, exact-match only mode

Rules: prefer backend.PriceBookService for logic; keep Streamlit thin;
replace_vendor on re-import; long-form rows; push to origin (pricebook-system);
never commit *.db or .venv.

Next: [UI polish / keep going / or name a feature]
```
