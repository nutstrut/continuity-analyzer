#!/bin/bash
set -euo pipefail

APP_DIR="/home/ubuntu/continuity-analyzer"
SERVICE_FILE="/etc/systemd/system/continuity-analyzer.service"
NGINX_SITE="/etc/nginx/sites-available/default"

mkdir -p "$APP_DIR"
cd "$APP_DIR"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

[ -f continuity_events_master.jsonl ] || touch continuity_events_master.jsonl
[ -f chain_events_master.jsonl ] || touch chain_events_master.jsonl
mkdir -p keys
chmod 700 keys
chmod 600 keys/*.json 2>/dev/null || true
chmod +x start.sh

cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=Continuity Analyzer Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/continuity-analyzer
ExecStart=/home/ubuntu/continuity-analyzer/venv/bin/uvicorn continuity_analyzer:app --host 127.0.0.1 --port 3002
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable continuity-analyzer.service
systemctl restart continuity-analyzer.service

echo "\nAdd the following nginx block INSIDE your active server { ... } block (not at file end):"
cat <<'EOF'
location /continuity/ {
    proxy_pass http://127.0.0.1:3002/continuity/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /.well-known/continuity-keys.json {
    proxy_pass http://127.0.0.1:3002/.well-known/continuity-keys.json;
    proxy_set_header Host $host;
}
EOF

if nginx -t >/dev/null 2>&1; then
  systemctl reload nginx
else
  echo "nginx config test failed; skipping reload until route block is inserted correctly"
fi

echo "continuity-analyzer deployed and running on 127.0.0.1:3002"
