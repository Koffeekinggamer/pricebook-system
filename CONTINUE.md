# FAF Pricebook — status

**Updated:** 2026-07-16  
**Folder:** `~/FAF-pricebook`  
**GitHub (private):** https://github.com/Koffeekinggamer/faf-pricebook-system

## Done

| Item | Status |
|------|--------|
| Full app (Search · Import · Batch · Quotes · Vendors · Admin) | ✅ |
| Backend + CLI | ✅ |
| Git repo + push to GitHub | ✅ `main` → `Koffeekinggamer/faf-pricebook-system` |
| Batch load Completed Excel Pricebooks | ✅ |
| Genuine Oak Master import | ✅ |
| Master DB populated | ✅ ~59,926 rows · 14 vendors · 243 collections |
| Sample quote + PDF | ✅ |

## Run

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py
```

## Git (HTTPS works via GitHub Desktop credentials)

```bash
cd ~/FAF-pricebook
git pull
git add -A && git commit -m "your message"
git push
```

SSH key add to GitHub still optional (`Permission denied` until public key is on the account). HTTPS push is working.

## Notes / later polish

- A few `.xls` files skipped (0 rows): LUXHOME WHOLESALE, AJ's LUxhome addon — may need manual map.
- Patio Kraft only got 1 row — layout needs a dedicated tweak.
- Premier markup detected as **1.0** — check that workbook’s markup sheet.
- HW_2025 and FN Chair imported large matrices — spot-check species pairing on the floor.
- Local DB (`master_pricebook.db`) is **not** on GitHub (gitignored).

## Resume prompt

```
Continue FAF Pricebook at ~/FAF-pricebook.
Repo: https://github.com/Koffeekinggamer/faf-pricebook-system
Master DB already loaded. Next: [your ask].
```
