# Deploy FAF Price Book (online access)

## Source of truth

| Asset | Location | Notes |
|-------|----------|--------|
| **Authoritative catalog** | `~/FAF-pricebook/master_pricebook.db` on the store Mac | **Never** committed to GitHub |
| **App code** | `origin` → `Koffeekinggamer/pricebook-system` | Safe to deploy |
| **Backups** | `~/Documents/FAF-pricebook-backups/` | Local only |

**Important:** Streamlit Cloud / Fly deploy the **code**, not the private ~500k-row DB (gitignored).  
Floor staff should use **local** or the **Mac public tunnel** for current prices.

---

## Recommended: local + Cloudflare quick tunnel

While this Mac is on (LaunchAgents keep Streamlit up):

| | |
|--|--|
| **Local** | http://127.0.0.1:8501 |
| **Public** | See `~/Documents/FAF-pricebook-backups/CURRENT_PUBLIC_URL.txt` |
| **Login** | Foothills / Amish |

Refresh the public URL anytime:

```bash
~/FAF-pricebook/scripts/public_tunnel.sh
# writes CURRENT_PUBLIC_URL.txt when successful
```

Or:

```bash
# ensure Streamlit on 8501 first
cloudflared tunnel --url http://127.0.0.1:8501 --no-autoupdate
# copy the https://….trycloudflare.com URL into CURRENT_PUBLIC_URL.txt
```

**Autostart (this Mac):**

```bash
~/FAF-pricebook/scripts/install_autostart.sh   # Streamlit + tunnel agents
~/FAF-pricebook/scripts/install_weekly_backup.sh
~/FAF-pricebook/scripts/install_viztech_monthly_sync.sh
```

---

## Streamlit Community Cloud (code only — empty/small DB unless you inject data)

Repo: https://github.com/Koffeekinggamer/pricebook-system

1. https://share.streamlit.io/deploy  
2. Repository `Koffeekinggamer/pricebook-system` · branch `main` · main file `pricebook_app.py`  
3. Secrets (optional):

```toml
[auth]
username = "Foothills"
password = "Amish"

# Viztech monthly sync does NOT run on Cloud (no LaunchAgent / no local downloads)
```

**Do not expect** the full store catalog on Cloud without a separate DB upload strategy (not implemented).

---

## Fly.io (Docker — same DB limitation)

```bash
export PATH="$HOME/.fly/bin:$PATH"
fly auth login
cd ~/FAF-pricebook
fly deploy -a faf-pricebook
```

App name in `fly.toml`: `faf-pricebook`.  
Without mounting/uploading `master_pricebook.db`, the Fly app will not match the floor Mac.

---

## Viztech monthly catalog refresh (floor Mac)

```bash
.venv/bin/python scripts/viztech_sync.py --dry-run
.venv/bin/python scripts/viztech_sync.py
```

Schedule: LaunchAgent `com.faf.pricebook.viztech-sync` every ~30 days.  
Credentials: `.streamlit/secrets.toml` `[viztech]` (gitignored).

---

## Decision matrix

| Need | Use |
|------|-----|
| Floor sales today, full book | **Local 8501** or **quick tunnel** |
| Permanent public marketing demo | Cloud/Fly with a **sanitized sample DB** (not full wholesale) |
| Keep prices private | Never commit `*.db`; use Mac tunnel only for staff |
