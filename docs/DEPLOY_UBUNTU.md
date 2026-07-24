# Deploying to an Ubuntu Server

Two paths: **Docker Compose** (recommended — the project already ships
this) or **native** (systemd services + nginx, no Docker). Docker Compose
is simpler to keep updated and matches exactly what you tested locally.

---

## Option A — Docker Compose (recommended)

### 1. Install Docker on the server

```bash
# Ubuntu 22.04/24.04
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out/in so the group change takes effect

docker --version
docker compose version
```

### 2. Get the project onto the server

```bash
# via git
git clone <your-repo-url> firewall-converter
cd firewall-converter

# or if you're copying the zip instead
scp firewall-config-converter-phase1.zip user@your-server:~
ssh user@your-server
unzip firewall-config-converter-phase1.zip && cd converter
```

### 3. Configure for your server's address

Edit `docker-compose.yml` and set `CORS_ORIGINS` to wherever the
frontend will actually be reached from — your server's IP or domain,
not `localhost`:

```yaml
environment:
  - CORS_ORIGINS=http://your-server-ip:3000
  # or, once you have a domain + reverse proxy (step 6):
  # - CORS_ORIGINS=https://converter.yourdomain.com
```

### 4. Build and start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend    # watch startup logs
```

### 5. Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

From another machine: `http://your-server-ip:3000` should load the UI.
If it doesn't, check your cloud provider's security group / firewall
rules, not just `ufw` on the box itself.

### 6. Open the firewall (if using `ufw`)

```bash
sudo ufw allow 3000/tcp   # frontend
sudo ufw allow 8000/tcp   # backend (only needed if you hit the API directly / Swagger)
sudo ufw enable
sudo ufw status
```

If you're putting this behind nginx + a domain (recommended for anything
beyond quick testing — see below), you only need to open 80/443
externally and can keep 3000/8000 bound to localhost only.

### 7. Put it behind nginx + a domain + TLS (recommended beyond testing)

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

Change the compose file to only bind these ports to localhost, so nginx
is the only public entry point:

```yaml
# docker-compose.yml
services:
  backend:
    ports:
      - "127.0.0.1:8000:8000"
  frontend:
    ports:
      - "127.0.0.1:3000:3000"
```

Then:

```bash
sudo tee /etc/nginx/sites-available/converter <<'EOF'
server {
    listen 80;
    server_name converter.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/converter /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d converter.yourdomain.com
```

(The frontend's own nginx container already proxies `/api/*` to the
backend container over the Docker network, so you don't need a separate
`/api` location block here — the host nginx only needs to reach the
frontend container.)

Update `CORS_ORIGINS` in `docker-compose.yml` to
`https://converter.yourdomain.com`, then:

```bash
docker compose up -d --build
```

### 8. Keep it running across reboots

Docker's `restart: unless-stopped` is already set in `docker-compose.yml`
for both services, and the Docker daemon itself starts on boot via
systemd — so a server reboot brings the stack back up automatically. No
extra step needed.

### 9. Updating later

```bash
cd firewall-converter
git pull            # or re-upload the new zip
docker compose up -d --build
```

### 10. Backups

The SQLite DB and generated outputs live in the `backend_storage`
named volume. To back it up:

```bash
docker run --rm -v converter_backend_storage:/data -v $(pwd):/backup \
  alpine tar czf /backup/storage-backup.tar.gz -C /data .
```

---

## Option B — Native (no Docker)

Only worth it if you specifically want to avoid Docker. More moving
parts to maintain yourself (process supervision, Node/Python version
pinning).

### 1. Install prerequisites

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv nginx

curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Backend as a systemd service

```bash
cd /opt
sudo git clone <your-repo-url> firewall-converter
cd firewall-converter/backend

python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
deactivate
```

```bash
sudo tee /etc/systemd/system/fwconverter-backend.service <<'EOF'
[Unit]
Description=Firewall Config Converter - Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/firewall-converter/backend
Environment=DATABASE_URL=sqlite:////opt/firewall-converter/backend/storage/converter.db
Environment=CORS_ORIGINS=https://converter.yourdomain.com
ExecStart=/opt/firewall-converter/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo mkdir -p /opt/firewall-converter/backend/storage
sudo chown -R www-data:www-data /opt/firewall-converter

sudo systemctl daemon-reload
sudo systemctl enable --now fwconverter-backend
sudo systemctl status fwconverter-backend
```

### 3. Build the frontend as static files

```bash
cd /opt/firewall-converter/frontend
npm install
VITE_API_BASE=/api npm run build
```

### 4. Serve everything through nginx

```bash
sudo tee /etc/nginx/sites-available/converter <<'EOF'
server {
    listen 80;
    server_name converter.yourdomain.com;

    root /opt/firewall-converter/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/converter /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d converter.yourdomain.com
```

### 5. Updating later

```bash
cd /opt/firewall-converter
sudo git pull
cd backend && . .venv/bin/activate && pip install -r requirements.txt && deactivate
sudo systemctl restart fwconverter-backend
cd ../frontend && npm install && VITE_API_BASE=/api npm run build
```

---

## Which one for "just testing"?

Docker Compose, unmodified, no nginx/TLS/domain — just:

```bash
docker compose up -d --build
```

then hit `http://your-server-ip:3000` directly (open port 3000 in your
firewall/security group). Add nginx + TLS once you're past testing and
want a real domain in front of it.
