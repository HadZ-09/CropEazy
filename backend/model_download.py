"""Download ML models when Git LFS files are unavailable (Railway, etc.)."""

import os
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIN_MODEL_BYTES = 1000

GITHUB_OWNER = os.getenv("GITHUB_REPO_OWNER", "HadZ-09")
GITHUB_REPO = os.getenv("GITHUB_REPO_NAME", "CropEazy")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")


def resolve_model_dir() -> Path:
    if os.getenv("MODEL_DIR"):
        configured = Path(os.getenv("MODEL_DIR"))
        return configured if configured.is_absolute() else PROJECT_ROOT / configured

    bundled = PROJECT_ROOT / "models"
    yield_file = bundled / os.getenv("YIELD_MODEL_NAME", "model.joblib")
    if yield_file.exists() and yield_file.stat().st_size >= MIN_MODEL_BYTES:
        return bundled

    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return Path("/tmp/models")

    return bundled


def model_paths() -> tuple[Path, Path]:
    model_dir = resolve_model_dir()
    yield_path = model_dir / os.getenv("YIELD_MODEL_NAME", "model.joblib")
    crop_path = model_dir / os.getenv("CROP_MODEL_NAME", "crop_recommendation_model.pkl")
    return yield_path, crop_path


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
    yield_path, crop_path = model_paths()
    targets = [
        (yield_path, f"models/{yield_path.name}"),
        (crop_path, f"models/{crop_path.name}"),
    ]

    for dest, rel_path in targets:
        if _needs_download(dest):
            _download(_media_url(rel_path), dest)
        else:
            print(f"Model OK: {dest.name} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    ensure_model_files()
