# FAF Pricebook — pause note (resume later)

**Saved:** 2026-07-16  
**Product:** FAF (Foothills Amish Furniture) Price Book System  
**Local folder:** `~/FAF-pricebook` (renamed from `pricebook-system`)

## What’s done

- Full app v2: Search · Import · Batch · Quotes · Vendors · Admin
- Backend: `PriceBookService`, upsert, batch, quotes, CLI
- Wide Excel unpivot + PDF import parsers
- Git repo on `main` (2 commits; clean working tree)
- SSH key created on this Mac (`~/.ssh/id_ed25519.pub`)
- `.gitignore` keeps `.venv` and `*.db` off GitHub

## Not finished (next session)

1. **Add SSH public key to GitHub** → [github.com/settings/keys](https://github.com/settings/keys)  
   Then: `ssh -T git@github.com` (expect: `Hi USERNAME!`)
2. **Publish private repo** `faf-pricebook-system`  
   - GitHub Desktop: Add Local Repository → this folder → **Publish repository** (Private)  
   - Or: `git remote add origin git@github.com:USERNAME/faf-pricebook-system.git && git push -u origin main`
3. Optional: batch-load Completed Excel Pricebooks into master DB
4. Optional: use Quotes on the floor

## Run the app

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py
```

## Resume prompt for Grok

```
Continue FAF Pricebook at ~/FAF-pricebook.
Read CONTINUE.md and README.md. Pick up where we left off (GitHub publish / batch load / whatever I ask).
```

## Important paths

| What | Where |
|------|--------|
| Code | `~/FAF-pricebook` |
| Local price DB | `~/FAF-pricebook/master_pricebook.db` (not in git) |
| Layout study | `LAYOUT_SYSTEM.md` |
| Prompt library | `PROMPTS.md` |
| SSH public key | `~/.ssh/id_ed25519.pub` |
