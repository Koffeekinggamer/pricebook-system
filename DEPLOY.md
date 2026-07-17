# Deploy FAF Price Book (online access)

## Live public access (working now)

While this Mac is on (autostart enabled):

| | |
|--|--|
| **Public URL** | See `~/Documents/FAF-pricebook-backups/CURRENT_PUBLIC_URL.txt` |
| **Local** | http://localhost:8501 |
| **Login** | Foothills / Amish |

Restart tunnel anytime:

```bash
~/FAF-pricebook/scripts/public_tunnel.sh
# or
ssh -R 80:127.0.0.1:8501 nokey@localhost.run
```

## Streamlit Community Cloud (permanent `*.streamlit.app`)

Repo is **public**: https://github.com/Koffeekinggamer/pricebook-system

1. Open https://share.streamlit.io/deploy
2. Sign in with GitHub as **Koffeekinggamer**
3. Fill in:
   - Repository: `Koffeekinggamer/pricebook-system`
   - Branch: `main`
   - Main file path: `pricebook_app.py`
   - App URL (optional): `faf-pricebook`
4. Deploy
5. Settings → Secrets (optional — defaults work):

```toml
[auth]
username = "Foothills"
password = "Amish"
```

## Fly.io (Docker, permanent)

```bash
export PATH="$HOME/.fly/bin:$PATH"
fly auth login
cd ~/FAF-pricebook
fly launch --copy-config --name faf-pricebook --region iad --yes
fly deploy
```

Dockerfile + fly.toml are in the repo.
