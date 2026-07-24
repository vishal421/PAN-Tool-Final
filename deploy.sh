#!/usr/bin/env bash
#
# Fresh-install script for the Firewall Config Converter stack.
# Run this from inside the unzipped project folder (where docker-compose.yml
# lives). Safe to re-run - it won't overwrite secrets that are already set.
#
# Usage:
#   bash deploy.sh
#   ROOT_DOMAIN=pan-tool.com ADMIN_EMAIL=you@yourcompany.com bash deploy.sh
#
# What this does NOT cover: Cloudflare Tunnel / DNS / reverse proxy setup -
# that's a separate step after this script finishes.

set -euo pipefail

echo "== Firewall Config Converter - install =="
echo

# --- 0. Must be run from the project root -------------------------------
if [ ! -f docker-compose.yml ]; then
  echo "ERROR: docker-compose.yml not found in the current directory."
  echo "cd into the unzipped project folder first, then re-run this script."
  exit 1
fi

# --- 1. System packages --------------------------------------------------
echo "-- Installing base packages --"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg unzip python3

# --- 2. Docker -------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "-- Installing Docker --"
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER"
  sudo systemctl enable docker
  NEEDS_RELOGIN=1
  echo "Docker installed."
else
  echo "-- Docker already installed, skipping --"
  NEEDS_RELOGIN=0
fi

# If this shell's group membership hasn't picked up 'docker' yet (fresh
# install in this same session), re-exec the rest under 'sg docker' so the
# script can keep running without requiring a manual logout/login.
if [ "${NEEDS_RELOGIN:-0}" = "1" ] && ! groups | grep -qw docker; then
  echo "Re-launching with the new docker group applied..."
  exec sg docker "$0" "$@"
fi

# --- 3. .env setup -----------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "-- Created .env from .env.example --"
fi

set_env_var() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}
get_env_var() {
  grep -oP "^${1}=\K.*" .env 2>/dev/null || true
}

# Secrets: generate only if not already set (so re-running this script never
# rotates existing secrets out from under a running deployment).
if [ -z "$(get_env_var POSTGRES_PASSWORD)" ]; then
  set_env_var POSTGRES_PASSWORD "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  echo "-- Generated POSTGRES_PASSWORD --"
fi
if [ -z "$(get_env_var JWT_SECRET)" ]; then
  set_env_var JWT_SECRET "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  echo "-- Generated JWT_SECRET --"
fi

# Worker count sized to this machine's CPU cores: (cores x 2) + 1, capped at 12.
CPU_COUNT=$(nproc)
WORKERS=$(( CPU_COUNT * 2 + 1 ))
[ "$WORKERS" -gt 12 ] && WORKERS=12
set_env_var WEB_CONCURRENCY "$WORKERS"
echo "-- Detected ${CPU_COUNT} CPU cores -> WEB_CONCURRENCY=${WORKERS} --"

# Storage paths - override by exporting STORAGE_BASE before running this
# script if you want data on a specific mount (e.g. your 500GB SSD).
STORAGE_BASE="${STORAGE_BASE:-$(pwd)/data}"
mkdir -p "${STORAGE_BASE}/postgres" "${STORAGE_BASE}/backend-storage"
set_env_var POSTGRES_DATA_PATH "${STORAGE_BASE}/postgres"
set_env_var STORAGE_PATH "${STORAGE_BASE}/backend-storage"
echo "-- Data will live under ${STORAGE_BASE} --"

# Optional: subdomain deployment (login./signup./dash.<domain>). Pass
# ROOT_DOMAIN=yourdomain.com as an env var to this script to configure it;
# otherwise this is skipped and .env keeps whatever's already there
# (blank = plain single-origin deployment).
if [ -n "${ROOT_DOMAIN:-}" ]; then
  set_env_var ROOT_DOMAIN "${ROOT_DOMAIN}"
  set_env_var COOKIE_DOMAIN ".${ROOT_DOMAIN}"
  set_env_var CORS_ORIGINS "https://${ROOT_DOMAIN},https://login.${ROOT_DOMAIN},https://signup.${ROOT_DOMAIN},https://dash.${ROOT_DOMAIN}"
  echo "-- Configured subdomain routing for ${ROOT_DOMAIN} --"
fi

# Optional: first admin account. Pass ADMIN_EMAIL=you@yourcompany.com to
# this script; that email auto-becomes admin the moment it signs up.
if [ -n "${ADMIN_EMAIL:-}" ]; then
  set_env_var ADMIN_BOOTSTRAP_EMAILS "${ADMIN_EMAIL}"
  echo "-- Set ADMIN_BOOTSTRAP_EMAILS=${ADMIN_EMAIL} --"
fi

echo
echo "-- Current .env (contains secrets - keep this file private) --"
echo "----------------------------------------------------------------"
cat .env
echo "----------------------------------------------------------------"
echo

# --- 4. Build and start ---------------------------------------------------
echo "-- Building and starting containers (this can take a few minutes the first time) --"
docker compose up -d --build

# --- 5. Health check --------------------------------------------------------
echo "-- Waiting for services to come up --"
sleep 8
docker compose ps
echo

echo -n "Backend health:  "
curl -fsS http://localhost:8000/api/health || echo "(not reachable yet - check: docker compose logs backend)"
echo -n "Frontend:        "
curl -fsS -o /dev/null -w "status %{http_code}\n" http://localhost:4757/ || echo "(not reachable yet - check: docker compose logs frontend)"

echo
echo "== Install complete =="
echo "Useful commands:"
echo "  docker compose ps          # container status"
echo "  docker compose logs -f     # follow logs"
echo "  docker compose down        # stop everything"
echo "  docker compose up -d       # start again (no rebuild)"
echo
echo "Next step: point a reverse proxy / Cloudflare Tunnel at this server's port 4757."
