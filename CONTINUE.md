# FAF Pricebook — LIVE

**Updated:** 2026-07-17  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/pricebook-system  
**Status:** LIVE · floor search ranked · collections cleaned · **~29,631 rows · 13 vendors**

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

## Next prompt

```
Continue FAF Pricebook at ~/FAF-pricebook (live, standardized).
Repo: https://github.com/Koffeekinggamer/pricebook-system
DB: ~/FAF-pricebook/master_pricebook.db (~30k rows, 13 vendors).
Backup: python -m backend.cli backup-db
Next: [your ask]
```
