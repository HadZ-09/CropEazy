# Deployment guide

## Do not use Vercel for CropEazy

Vercel is built for **small serverless functions** (API routes, Next.js). CropEazy is a **long-running FastAPI app with a 112 MB ML model**. Vercel will keep crashing no matter how many entrypoint fixes we apply.

### Why Vercel crashes (every time)

| Problem | Detail |
|--------|--------|
| **Bundle too large** | `model.joblib` (~108 MB) + scikit-learn + pandas + numpy ≈ **300–400 MB** deployed. Vercel’s default limit is **250 MB** per function. |
| **Not enough RAM** | Loading the sklearn model into memory needs **~1–2 GB RAM**. Vercel serverless caps at **1024–3008 MB** and shares it with the Python runtime — often OOM on cold start. |
| **Timeout** | First request must download + load the model. That can take **2+ minutes**. Vercel max is **60–300 seconds**, then the function is killed. |
| **No Git LFS** | Vercel doesn’t pull LFS files. We added a download script, but the model still must fit in the serverless bundle or re-download to `/tmp` on every cold start. |
| **Ephemeral disk** | `/tmp` is wiped when the function sleeps. SQLite DB and cached models don’t persist. |
| **Wrong architecture** | Vercel = spin up → handle one request → spin down. ML inference apps need a **always-on server** (Render, Railway, Koyeb). |

**Bottom line:** Use **Render** (you already have this working) or **Railway**. Do not redeploy on Vercel.

---

## Recommended: Render (already configured)

Your `/health` response on Render proves the API works. Stay on Render.

1. Dashboard: [render.com](https://render.com) → your **cropeazy** service  
2. Ensure latest commit is deployed (auto-deploy from GitHub `main`)  
3. Env vars: `JWT_SECRET`, `DEV_MODE=true`, `SKIP_MODEL_PRELOAD=true`  
4. Open your `*.onrender.com` URL  

**Verify**

- `/health` → `"status":"ok"`, `"models_on_disk":true`  
- `/api/status` → JSON  
- Crop prediction → works after first slow load (free tier = 512 MB RAM)  
- Yield prediction → may need paid plan (more RAM)  

Config file: `render.yaml`

---

## Alternative: Railway (more RAM, better for full ML)

1. [railway.app](https://railway.app) → **New Project** → GitHub → **CropEazy**  
2. Uses `railway.toml` automatically  
3. Variables: `JWT_SECRET`, `DATABASE_PATH=/data/cropeazy.db`, `DEV_MODE=true`  
4. Add **Volume** mounted at `/data` for persistent SQLite  
5. **Generate Domain**  

Railway handles large builds better than Vercel and doesn’t use serverless timeouts.

---

## Alternative: Koyeb (free, often no card)

See README → “Option B — Koyeb”.

---

## Local + public URL (no cloud, no card)

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cloudflared tunnel --url http://127.0.0.1:8000
```

---

## Platform comparison

| Platform | CropEazy fit | Free tier | Card required? |
|----------|--------------|-----------|----------------|
| **Render** | Good | 512 MB RAM, slow cold start | Sometimes (verify only) |
| **Railway** | Best | Trial / paid | Usually yes |
| **Koyeb** | Good | 512 MB RAM | Often no |
| **Vercel** | **Poor — don’t use** | N/A | Yes |
| **Cloudflare Tunnel** | Good (local PC) | Free | No |
