# Deploying to Render.com

Two services: **backend** (Docker web service) and **frontend** (static site).
Render builds directly from a Git repo, so push this project to GitHub/GitLab/
Bitbucket first.

## Option A — One-click Blueprint (recommended)

1. Push this repo to GitHub.
2. Edit `render.yaml` at the project root: replace both `repo:` values with
   your actual repo URL.
3. In the Render dashboard: **New → Blueprint**, point it at your repo.
   Render reads `render.yaml` and provisions both services together.
4. First deploy will fail on the cross-referenced URLs (backend doesn't
   know the frontend's URL yet, and vice versa) — that's expected. Once
   both services have their `onrender.com` URLs assigned:
   - Backend service → **Environment** → set `CORS_ORIGINS` to your actual
     frontend URL, e.g. `https://fwconverter-frontend.onrender.com`
   - Frontend service → **Environment** → set `VITE_API_BASE` to your
     actual backend URL + `/api`, e.g.
     `https://fwconverter-backend.onrender.com/api`
   - Trigger **Manual Deploy** on both so the new env vars take effect
     (`VITE_API_BASE` is baked in at build time for Vite, so the frontend
     needs a rebuild, not just a restart).

## Option B — Manual setup (no render.yaml)

**Backend**
1. **New → Web Service** → connect your repo.
2. Runtime: **Docker**. Root/Dockerfile path: `backend/Dockerfile`,
   Docker context: `backend`.
3. Instance type: anything above the free tier (free web services on
   Render don't support persistent disks, and this app needs one for
   SQLite to survive restarts/deploys — see note below).
4. Add a **Disk**: mount path `/app/storage`, size 1GB is plenty to start.
5. Environment variables:
   - `DATABASE_URL` = `sqlite:////app/storage/converter.db`
   - `MAX_UPLOAD_MB` = `25`
   - `CORS_ORIGINS` = (fill in after frontend exists, see below)
6. Health check path: `/api/health`.
7. Deploy. Note the resulting URL, e.g. `https://fwconverter-backend.onrender.com`.

**Frontend**
1. **New → Static Site** → connect your repo.
2. Build command: `cd frontend && npm install && npm run build`
3. Publish directory: `frontend/dist`
4. Add a rewrite rule so client-side routing works: source `/*` →
   destination `/index.html`.
5. Environment variable: `VITE_API_BASE` = `https://<your-backend-url>/api`
   (from the step above). Vite env vars are read at **build time**, so
   set this before the first build.
6. Deploy. Note the resulting URL, e.g. `https://fwconverter-frontend.onrender.com`.

**Close the loop**
- Go back to the backend service → Environment → set `CORS_ORIGINS` to
  the frontend URL from step 6 → save (triggers a redeploy automatically).

## Why a persistent disk (not free tier)

Render's free/standard web services use an ephemeral filesystem — every
deploy or restart wipes local files. This project stores its job
database and generated output files in `backend/storage/` via SQLite,
so without a Disk attached, conversion history disappears on every
redeploy or scale event. Attach a Disk to the backend service (Option A
does this automatically; Option B step 4) to persist it.

**Alternative:** if you'd rather not pay for a disk, swap SQLite for
Render's managed PostgreSQL and point uploaded/generated files at
object storage (e.g. S3-compatible). That's a bigger change than this
project needs for now — the disk is the simplest path for a
single-instance internal tool.

## CORS gotcha

The backend explicitly allowlists origins via `CORS_ORIGINS` (see
`app/core/config.py`) rather than using `*`, since the frontend sends
`multipart/form-data` uploads. If you see CORS errors in the browser
console after deploying, it almost always means `CORS_ORIGINS` on the
backend doesn't exactly match the frontend's `https://...onrender.com`
URL (protocol + host, no trailing slash).

## Verifying the deploy

```bash
curl https://<your-backend>.onrender.com/api/health
# {"status":"ok"}
```

Then open the frontend URL in a browser and confirm the vendor tiles
load (they'll show "Coming soon" until a vendor parser is registered —
that's expected at this phase).

## Scaling note

Render's Docker web services can idle/sleep on lower tiers, which means
a cold start delay on the first request after inactivity. If that
matters for your use case, pick an "always on" instance type.
