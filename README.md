# CropEazy — Crop Intelligence Platform

AI-powered crop recommendation, yield prediction in tonnes, pest calendar, emergency SMS alerts, and profit/loss dashboard in INR.

## Features

- **Crop recommendation** from soil nutrients and climate (N, P, K, pH, temperature, humidity, rainfall)
- **Production prediction** in tonnes from farm area and regional parameters
- **GPS auto-fill** for location, temperature, and rainfall
- **Pest prediction** by season and month
- **Emergency calamity SMS alerts** (Twilio in production, console in dev mode)
- **OTP login** — separate dashboard per farmer
- **Profit / loss dashboard** in Indian Rupees (₹)

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then edit secrets

# Train models if needed
python backend/training.py
python backend/train_crop_model.py

# Run server
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**

## Environment variables

Copy `.env.example` to `.env` locally. **Never commit `.env`.**

| Variable | Description |
|---|---|
| `JWT_SECRET` | Secret for auth tokens |
| `DEV_MODE` | `true` logs OTP/SMS to console |
| `TWILIO_*` | Optional — real SMS in production |

## Deploy to Vercel

1. Push this repo to GitHub (`.env` is gitignored)
2. Import the project on [vercel.com](https://vercel.com)
3. Add environment variables from `.env.example`
4. Deploy — Vercel runs `api/index.py` (FastAPI)

> ML model files are tracked with **Git LFS** because `model.joblib` exceeds GitHub's 100 MB limit.

## Project structure

```
backend/          FastAPI app, ML models, auth, alerts
front_end/        HTML, CSS, JavaScript UI
models/           Trained model files (Git LFS)
dataset/          Training CSV files
api/index.py      Vercel serverless entrypoint
```

## Tech stack

- FastAPI + scikit-learn
- SQLite (local / Vercel `/tmp`)
- Vanilla JS frontend
- Open-Meteo + Nominatim for GPS weather
- Twilio (optional) for SMS
