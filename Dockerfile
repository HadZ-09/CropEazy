FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git git-lfs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -m backend.model_download

ENV PORT=8000
EXPOSE 8000

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
