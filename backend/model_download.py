"""Download ML models when Git LFS files are unavailable (Railway, etc.)."""

import os
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / os.getenv("MODEL_DIR", "models")
YIELD_MODEL_PATH = MODEL_DIR / os.getenv("YIELD_MODEL_NAME", "model.joblib")
CROP_MODEL_PATH = MODEL_DIR / os.getenv("CROP_MODEL_NAME", "crop_recommendation_model.pkl")

GITHUB_OWNER = os.getenv("GITHUB_REPO_OWNER", "HadZ-09")
GITHUB_REPO = os.getenv("GITHUB_REPO_NAME", "CropEazy")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
MIN_MODEL_BYTES = 1000


def _media_url(relative_path: str) -> str:
    return (
        f"https://media.githubusercontent.com/media/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{relative_path}"
    )


def _needs_download(path: Path) -> bool:
    return not path.exists() or path.stat().st_size < MIN_MODEL_BYTES


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    print(f"Downloading model: {url}")

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0 and block_num % 500 == 0:
            pct = min(100, block_num * block_size * 100 // total_size)
            print(f"  {dest.name}: ~{pct}%")

    urllib.request.urlretrieve(url, tmp, reporthook=_report)

    size = tmp.stat().st_size
    if size < MIN_MODEL_BYTES:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file too small ({size} bytes). "
            f"Git LFS pointer received instead of model: {url}"
        )

    tmp.replace(dest)
    print(f"Saved {dest.name} ({size:,} bytes)")


def ensure_model_files() -> None:
    model_rel = MODEL_DIR.relative_to(PROJECT_ROOT).as_posix()
    targets = [
        (YIELD_MODEL_PATH, f"{model_rel}/{YIELD_MODEL_PATH.name}"),
        (CROP_MODEL_PATH, f"{model_rel}/{CROP_MODEL_PATH.name}"),
    ]

    for dest, rel_path in targets:
        if _needs_download(dest):
            _download(_media_url(rel_path), dest)
        else:
            print(f"Model OK: {dest.name} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    ensure_model_files()
