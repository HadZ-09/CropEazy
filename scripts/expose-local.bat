@echo off
REM Free public URL for your local CropEazy server — no credit card, no cloud host.
REM 1. Start the app in another terminal:
REM    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
REM 2. Run this script:
REM    scripts\expose-local.bat

echo Starting Cloudflare quick tunnel to http://127.0.0.1:8000 ...
echo Share the https://*.trycloudflare.com URL it prints.
echo Press Ctrl+C to stop.

cloudflared tunnel --url http://127.0.0.1:8000
