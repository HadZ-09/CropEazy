# CropEazy — Crop Intelligence Platform

Full-stack crop recommendation, yield prediction, pest alerts, OTP login, and profit/loss dashboard. Frontend and API run together on one service.

## Deploy on Render (recommended alternative to Vercel)

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New** → **Blueprint** → connect repo **HadZ-09/CropEazy**.
3. Render reads `render.yaml` automatically (downloads models at build, starts uvicorn, `/health` check).
4. Use at least the **Starter** plan (512MB+ RAM needed for sklearn + 108MB model).
5. After deploy, open your `*.onrender.com` URL.

Verify: `https://YOUR-APP.onrender.com/health` → `yield_model_loaded: true`.

Optional env vars in the Render dashboard: `JWT_SECRET` (auto-generated), Twilio keys for SMS.

---

## Deploy on Railway

### 1. Push code (already on GitHub)

Repo: https://github.com/HadZ-09/CropEazy

ML models are stored with **Git LFS** on GitHub. **Railway does not pull LFS files**, so the build runs `python -m backend.model_download` to fetch models from GitHub instead.

### 2. Create the Railway project

1. Go to [railway.app](https://railway.app) and sign in.
2. **New Project** → **Deploy from GitHub repo** → select **CropEazy**.
3. Railway reads `railway.toml` automatically (Nixpacks build, uvicorn start, `/health` check).

### 3. Environment variables

In the service **Variables** tab, set:

| Variable | Value |
|----------|--------|
| `JWT_SECRET` | Long random string (required for login) |
| `DATABASE_PATH` | `/data/cropeazy.db` |
| `DEV_MODE` | `true` to log OTPs in Railway logs instead of SMS (optional for testing) |

Optional SMS (Twilio): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.

### 4. Persistent database volume

1. Open your service → **Volumes** → **Add Volume**.
2. Mount path: **`/data`**
3. Redeploy so SQLite survives restarts.

### 5. Public URL

**Settings** → **Networking** → **Generate Domain**. Open that URL — the app and API share the same origin (no separate frontend host).

### 6. Verify deployment

Visit `https://YOUR-DOMAIN.up.railway.app/health`. You should see:

```json
{
  "status": "ok",
  "yield_model_loaded": true,
  "crop_model_loaded": true,
  "yield_model_bytes": 108000000
}
```

If `yield_model_bytes` is ~130, models failed to download — check build logs for `python -m backend.model_download`.

## Local development

```powershell
pip install -r requirements.txt
git lfs pull
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

Copy `.env.example` to `.env` and set `JWT_SECRET`. Use `DEV_MODE=true` to print OTP codes in the terminal.

## CLI (optional)

```powershell
npm install -g @railway/cli
railway login
railway link
railway up
```
