# FAF Pricebook

**Foothills Amish Furniture** — private multiplier engine for builder wholesale lists, retail pricing, search, and customer quotes.

Streamlit + SQLite. Default retail multiplier **2.7×** (adjustable per vendor).

**Builders ship wide species matrices. We store long-form rows**  
(one row = SKU × species tier × finish).

> **Status:** LIVE — master data loaded (~41k rows, 13 vendors). See **CONTINUE.md**.  
> **Folder:** `~/FAF-pricebook`  
> **GitHub:** private repo [Koffeekinggamer/pricebook-system](https://github.com/Koffeekinggamer/pricebook-system)  
> Local `*.db` and `.venv` are gitignored (price book stays on this machine).

## Quick start

```bash
cd ~/FAF-pricebook
python3 -m venv .venv   # only if venv missing
source .venv/bin/activate
pip install -r requirements.txt
streamlit run pricebook_app.py
```

Open `http://localhost:8501`.

## App tabs (v2)

| Tab | What |
|-----|------|
| **Search** | Multi-token search, export Excel/CSV/PDF, add hit to quote |
| **Import** | One Excel/PDF — wide unpivot, markup detect, upsert |
| **Batch** | Whole folder of builder books |
| **Quotes** | Customer quotes, lines, totals, PDF/Excel |
| **Vendors** | Per-vendor multipliers + recompute |
| **Admin** | Stats, duplicate scan/cleanup, delete by source |

## Architecture

```
pricebook_app.py          # UI only
backend/
  service.py              # PriceBookService facade
  repository.py           # catalog SQLite
  quotes.py               # quote tables + PDF
  batch.py                # folder import
  import_service.py       # Excel/PDF → rows
  normalize.py · export.py · db.py · models.py · cli.py
wide_import.py · pdf_import.py
master_pricebook.db
LAYOUT_SYSTEM.md · PROMPTS.md
```

## CLI

```bash
source .venv/bin/activate

python -m backend.cli stats
python -m backend.cli search "oak nightstand" --limit 20
python -m backend.cli vendors

# one file
python -m backend.cli import-xlsx "/path/list.xlsx" \
  --vendor "Genuine Oak" --use-markup --mode upsert

# whole folder (Completed Excel Pricebooks, etc.)
python -m backend.cli batch \
  "$HOME/Documents/Judson's old mac book pro/Downloads/Builder Updates 07172025/Ready for Web Upload/Completed Excel Pricebooks" \
  --excel-only --mode upsert

python -m backend.cli dups
python -m backend.cli cleanup-dups          # dry-run
python -m backend.cli cleanup-dups --execute
python -m backend.cli set-multiplier "FVWW" 2.7
```

## Commit modes

| Mode | Behavior |
|------|----------|
| **upsert** | Update existing identity; insert new (**default**) |
| **append** | Always insert |
| **replace_source** | Delete same filename, then insert |

**Identity** = vendor + collection + part + species + finish + option + dimensions

## Master row standard

All vendors share one field shape (wholesale base × mult → retail).  
See **STANDARDS.md**. Re-run anytime:

```bash
.venv/bin/python -m backend.cli standardize
```

## Layout rules

See `LAYOUT_SYSTEM.md`. Gold pattern:

```
Item # | Description | Dims | Wood tier 1 | Wood tier 2 | …
  → unpivot → long rows with species_tier 1..N
```

## Copy-paste prompts for Grok

See `PROMPTS.md`.
