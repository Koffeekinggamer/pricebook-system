# FAF Price Book

Foothills Amish Furniture — floor price book (Streamlit + SQLite).

## Live

| Access | URL |
|--------|-----|
| Local | http://localhost:8501 |
| GitHub | https://github.com/Koffeekinggamer/pricebook-system |
| Login | **Foothills** / **Amish** |

## Deploy (Streamlit Community Cloud)

Repo is **public**. On https://share.streamlit.io/deploy :

1. Repository: `Koffeekinggamer/pricebook-system`
2. Branch: `main`
3. Main file: `pricebook_app.py`
4. Optional secrets (defaults work without this):

```toml
[auth]
username = "Foothills"
password = "Amish"
```

See [DEPLOY.md](DEPLOY.md). Floor staff: [FLOOR_CHEAT_SHEET.md](FLOOR_CHEAT_SHEET.md).

## Local run

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py --server.port 8501
```

### Autostart on this Mac (Streamlit + public tunnel)

```bash
~/FAF-pricebook/scripts/install_autostart.sh
```

### Weekly DB backup

```bash
~/FAF-pricebook/scripts/install_weekly_backup.sh
```

Backups: `~/Documents/FAF-pricebook-backups/`

## Tabs

- **Search** — retail prices, pin builders, 150-row limit
- **Drop files** — import builder Excel/PDF (replace catalog)
- **Vendors** — per-builder multipliers
- **Admin** — backup / restore / cleanup

## Defaults

- Most builders: mult **2.7**
- Genuine Oak: **1.7**
- Retail = wholesale × multiplier
