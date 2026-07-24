# BPA Proxy — Local Server + Console

> **V15 note:** authentication is now fully backend-driven. There is no
> Client ID / Client Secret / TSG ID field in the UI anymore — the Prisma
> Access service account lives only in this server's environment
> (`CLIENT_ID` / `CLIENT_SECRET` / `TSG_ID`, see `.env.example`) and is
> never sent to or entered in the browser. End users just click
> **Generate Token** and the backend authenticates with Palo Alto for them.
>
> **V13 note:** this is deployed as its own app on its own subdomain
> (e.g. `bpa.pan-tool.com`), separate from the main Firewall Config
> Converter tool at `dash.pan-tool.com`. The BPA parsing/report-generation
> logic, upload/poll flow, and Excel export are untouched — only the
> authentication mechanism and its UI changed. It still has no
> account/session system of its own and never talks to the main app's
> backend or database.
>
> The default port also changed from **3000 → 4021** so it can run
> alongside the main stack (backend on 8000, frontend container on 4757)
> without clashing. Override with `PORT=xxxx npm start` as always.

Runs the full Palo Alto Networks BPA generation flow (token → upload config →
poll result) through a small Node.js server on your own machine. This solves
the browser CORS problem: your browser only ever talks to `localhost`, and
Node.js makes the real calls to Palo Alto server-to-server, exactly like `curl`.

## Requirements

- Node.js 18 or later (for built-in `fetch`)
  Check with: `node -v`
  If missing:
  ```
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ```

## Setup (one time)

1. Copy this whole `bpa-tool` folder onto your Ubuntu machine (or use the
   included `Dockerfile` / the `bpa-tool` service in the repo's root
   `docker-compose.yml`).
2. Open a terminal in that folder and install dependencies:
   ```
   npm install
   ```
3. Create a `.env` file in this folder (copy `.env.example`) with your
   Prisma Access service account:
   ```
   CLIENT_ID=your-client-id
   CLIENT_SECRET=your-client-secret
   TSG_ID=your-tsg-id
   ```
   These are read once at server startup and never exposed to the browser.
   If deploying via the root `docker-compose.yml` instead, set them in the
   repo root `.env` — see that file's BPA Tool section.

## Run

```
npm start
```
Now open `http://localhost:4021`.

## Deploying it as bpa.pan-tool.com

This folder has its own `Dockerfile` and is wired up as the `bpa-tool`
service in the project's root `docker-compose.yml`, exposed on port 4021.
To put it on its own subdomain:

1. Point `bpa.pan-tool.com`'s DNS at the host running this container.
2. Reverse-proxy that subdomain to `127.0.0.1:4021` (Caddy/nginx/Cloudflare
   Tunnel all work fine — it's a single plain HTTP origin, no special
   headers required).
3. Set `CLIENT_ID` / `CLIENT_SECRET` / `TSG_ID` in the repo root `.env` so
   docker-compose passes them into the container's environment.
4. That's it — this app doesn't need to know about `pan-tool.com`,
   `dash.pan-tool.com`, or anything else in the main stack. It's fully
   self-contained.

The `render.yaml` at the repo root also has a matching `bpa-report-generator`
service definition if you'd rather deploy it on Render — set the same three
env vars there in the Render dashboard.


You should see:
```
BPA Proxy running → http://localhost:4021
```

Open that URL in a browser **on the same machine** (or replace `localhost`
with the server's LAN IP if opening from another device on your network,
e.g. `http://192.168.1.50:4021`).

## Using the console

1. **Stage 1 — Authenticate**: click **Generate Token**. The backend reads
   the service account from its own environment and authenticates with
   Palo Alto silently — no credentials to type in.
2. **Stage 2 — Upload configuration file**: choose your device type, drag in
   the exported config `.xml`, click **Initiate & Upload**. The server gzips
   the file and pushes it to the presigned upload URL for you.
3. **Stage 3 — Generate BPA result**: click **Check Status**. If the status
   comes back `IN_PROGRESS`, just click it again after 30–60 seconds. Once it
   shows `COMPLETED`, the full JSON appears in the console pane and you can
   click **Download JSON** to save it.

## Notes / troubleshooting

- **Firewall**: this machine needs outbound HTTPS access to
  `auth.apps.paloaltonetworks.com` and `api.sase.paloaltonetworks.com`.
  If requests hang or fail immediately, check `sudo ufw status` and your
  organization's egress firewall rules.
- **Port already in use**: run on a different port with
  `PORT=4000 npm start`, then open `http://localhost:4000`.
- **Run in the background / keep alive after closing terminal**:
  ```
  nohup npm start > bpa-proxy.log 2>&1 &
  ```
  or, better, use `pm2`:
  ```
  sudo npm install -g pm2
  pm2 start server.js --name bpa-proxy
  ```
- **Field names differ**: the server looks for `upload_url`/`uploadUrl`/`url`
  and `id`/`report_id`/`reportId` in Palo Alto's response. If Stage 2 says
  "Unexpected response", open the browser dev tools Network tab, look at the
  `/api/initiate-upload` response, and tell me the actual field names —
  I'll adjust `server.js` accordingly.
- **Security**: the Prisma Access service account now lives only in this
  server's environment (`.env` / container env vars) — it's never sent to,
  entered in, or stored by the browser. If exposing this app beyond
  localhost, still put it behind your own authentication (e.g. an nginx
  reverse proxy with basic auth), since anyone who can reach the page can
  use it to generate BPA reports against your configured account.
