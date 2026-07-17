#!/bin/zsh
# Share local FAF Price Book on a public HTTPS URL (this Mac must stay on).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF="${HOME}/.local/bin/cloudflared"
PORT=8501

if ! curl -s -o /dev/null -w '' "http://127.0.0.1:${PORT}/"; then
  echo "Starting Streamlit on :${PORT}..."
  cd "$ROOT"
  nohup .venv/bin/streamlit run pricebook_app.py --server.headless true --server.port "$PORT" >/tmp/faf-streamlit.log 2>&1 &
  sleep 3
fi

if [[ ! -x "$CF" ]]; then
  echo "cloudflared missing at $CF"
  exit 1
fi

echo "Opening public tunnel → http://127.0.0.1:${PORT}"
echo "Login: Foothills / Amish"
exec "$CF" tunnel --url "http://127.0.0.1:${PORT}" --no-autoupdate
