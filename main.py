"""Vercel / default entrypoint — re-exports the FastAPI app."""
from backend.main import app

__all__ = ["app"]
