# Deploy FAF Price Book

## Option A — Streamlit Community Cloud (permanent URL)

1. Open https://share.streamlit.io/deploy (sign in with GitHub).
2. **Repository:** `Koffeekinggamer/pricebook-system` (private is OK if GitHub is connected).
3. **Branch:** `main`
4. **Main file path:** `pricebook_app.py`
5. **App URL** (optional): e.g. `faf-pricebook` → `https://faf-pricebook.streamlit.app`
6. Click **Deploy**.
7. **Settings → Secrets** — paste:

```toml
[auth]
username = "Foothills"
password = "Amish"
```

8. Save secrets and reboot the app if needed.
9. Confirm login works and Search shows ~30k+ rows.

**Note:** Free Community Cloud is fine for floor use. Keep the GitHub repo **private** (catalog data is in the repo for cloud seed).

## Option B — Public tunnel from this Mac (already scripted)

Requires this computer online with Streamlit running:

```bash
~/FAF-pricebook/scripts/public_tunnel.sh
```

Gives a temporary `https://….trycloudflare.com` URL. Login: Foothills / Amish.

## Local (always)

```bash
cd ~/FAF-pricebook
source .venv/bin/activate
streamlit run pricebook_app.py --server.port 8501
```

Open http://localhost:8501
