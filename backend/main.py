import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from joblib import load
from pydantic import BaseModel, Field

from backend.alert_service import check_and_notify_user
from backend.auth import get_current_user, send_login_otp, verify_login_otp
from backend.database import (
    add_dashboard_record,
    clear_dashboard_records,
    init_db,
    list_alert_logs,
    list_dashboard_records,
    upsert_alert_subscription,
)
from backend.location_service import get_location_context
from backend.model_download import ensure_model_files, model_paths
from backend.pest_data import get_pest_prediction

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))

YIELD_MODEL_PATH, CROP_MODEL_PATH = model_paths()
YIELD_DATASET_PATH = PROJECT_ROOT / os.getenv("DATASET_DIR", "dataset") / os.getenv(
    "YIELD_DATASET", "yield_df.csv"
)


def current_model_paths() -> tuple[Path, Path]:
    return model_paths()

yield_model: Any = None
crop_model: Any = None
yield_options: Dict[str, List[str]] = {"areas": [], "items": []}

CROP_PRICES_INR_PER_TONNE: Dict[str, float] = {
    "rice": 35000,
    "wheat": 24000,
    "maize": 21000,
    "corn": 21000,
    "potato": 18000,
    "potatoes": 18000,
    "tomato": 32000,
    "tomatoes": 32000,
    "banana": 28000,
    "cotton": 65000,
    "coffee": 220000,
    "grapes": 55000,
    "apple": 70000,
    "mango": 45000,
    "orange": 38000,
    "pigeonpeas": 62000,
    "chickpea": 54000,
    "lentil": 68000,
    "default": 25000,
}


def load_yield_options() -> None:
    global yield_options
    if yield_options.get("areas") or yield_options.get("items"):
        return
    if YIELD_DATASET_PATH.exists():
        df = pd.read_csv(YIELD_DATASET_PATH)
        yield_options = {
            "areas": sorted(df["Area"].dropna().astype(str).unique().tolist()),
            "items": sorted(df["Item"].dropna().astype(str).unique().tolist()),
        }


def _should_preload_models() -> bool:
    if os.getenv("SKIP_MODEL_PRELOAD", "").lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("RENDER") or os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return False
    return True


def load_models() -> None:
    global yield_model, crop_model, yield_options

    if yield_model is not None and crop_model is not None:
        return

    ensure_model_files()
    yield_path, crop_path = current_model_paths()

    if not yield_path.exists():
        raise RuntimeError(
            f"Yield model not found at {yield_path}. "
            "Ensure models are downloaded during build."
        )
    if not crop_path.exists():
        raise RuntimeError(
            f"Crop model not found at {crop_path}. "
            "Ensure models are downloaded during build."
        )

    if yield_path.stat().st_size < 1000:
        raise RuntimeError(
            "Yield model file looks like a Git LFS pointer, not the real model."
        )

    yield_model = load(yield_path)
    crop_model = load(crop_path)
    load_yield_options()


def ensure_models_loaded() -> None:
    try:
        load_models()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    load_yield_options()
    if _should_preload_models():
        try:
            load_models()
            yield_path, crop_path = current_model_paths()
            print(f"Loaded yield model from {yield_path}")
            print(f"Loaded crop model from {crop_path}")
        except Exception as exc:
            print(f"Model preload skipped: {exc}")
    else:
        print("Model preload disabled for this host (lazy load on first prediction).")
    yield


app = FastAPI(
    title="CropEazy Intelligence API",
    description="Crop recommendation, yield prediction, pest alerts, and farmer dashboard.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = PROJECT_ROOT / "front_end"


class SendOtpRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian mobile number")


class VerifyOtpRequest(BaseModel):
    phone: str
    otp: str
    name: str = "Farmer"


class CropPredictionRequest(BaseModel):
    N: float = Field(..., ge=0)
    P: float = Field(..., ge=0)
    K: float = Field(..., ge=0)
    temperature: float
    humidity: float = Field(..., ge=0, le=100)
    ph: float = Field(..., ge=0, le=14)
    rainfall: float = Field(..., ge=0)


class CropCandidate(BaseModel):
    crop: str
    confidence: float


class CropPredictionResponse(BaseModel):
    recommended_crop: str
    top_predictions: List[CropCandidate]


class YieldPredictionRequest(BaseModel):
    Area: str
    Item: str
    Year: int = Field(..., ge=1900, le=2100)
    farm_area_ha: float = Field(..., gt=0)
    avg_temp: float
    average_rain_fall_mm_per_year: float = Field(..., ge=0)
    pesticides_tonnes: float = Field(..., ge=0)


class YieldPredictionResponse(BaseModel):
    predicted_hg_ha_yield: float
    predicted_total_tonnes: float
    farm_area_ha: float
    input_data: YieldPredictionRequest


class ProfitRequest(BaseModel):
    crop: str
    predicted_tonnes: float = Field(..., gt=0)
    market_price_per_tonne: float = Field(..., ge=0, description="INR per tonne")
    farm_area_ha: float = Field(..., gt=0)
    pesticide_spend: float = Field(0, ge=0, description="INR spent on pesticides")
    seed_cost: float = Field(0, ge=0, description="INR")
    labor_cost: float = Field(0, ge=0, description="INR")
    fertilizer_cost: float = Field(0, ge=0, description="INR")
    region: str = ""


class ProfitResponse(BaseModel):
    currency: str = "INR"
    revenue: float
    total_costs: float
    net_profit: float
    profit_per_hectare: float
    margin_percent: float
    breakdown: Dict[str, float]


class DashboardRecordRequest(BaseModel):
    crop: str
    region: str = ""
    production_tonnes: float
    revenue: float
    costs: float
    profit: float
    margin: float
    data_json: Dict[str, Any] = Field(default_factory=dict)


class AlertSubscribeRequest(BaseModel):
    crop: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@app.get("/api/status")
def read_root() -> Dict[str, str]:
    return {
        "status": "online",
        "message": "CropEazy Intelligence API is running.",
        "frontend": "/",
        "currency": "INR",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    yield_path, crop_path = current_model_paths()
    models_on_disk = (
        yield_path.exists()
        and crop_path.exists()
        and yield_path.stat().st_size > 1000
        and crop_path.stat().st_size > 1000
    )
    return {
        "status": "ok",
        "yield_model_loaded": yield_model is not None,
        "crop_model_loaded": crop_model is not None,
        "models_on_disk": models_on_disk,
        "lazy_load": not _should_preload_models(),
        "message": (
            "Models load on first prediction (normal on Render free tier)."
            if not _should_preload_models() and not yield_model
            else "Models are loaded in memory."
            if yield_model and crop_model
            else "Waiting for first prediction to load models."
        ),
        "yield_model_path": str(yield_path),
        "yield_model_exists": yield_path.exists(),
        "yield_model_bytes": yield_path.stat().st_size if yield_path.exists() else 0,
    }


@app.post("/auth/send-otp")
def auth_send_otp(payload: SendOtpRequest) -> Dict[str, Any]:
    try:
        return send_login_otp(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/auth/verify-otp")
def auth_verify_otp(payload: VerifyOtpRequest) -> Dict[str, Any]:
    try:
        return verify_login_otp(payload.phone, payload.otp, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/me")
def auth_me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"id": user["id"], "phone": user["phone"], "name": user["name"]}


@app.get("/options/yield")
def get_yield_options() -> Dict[str, List[str]]:
    load_yield_options()
    return yield_options


@app.get("/options/prices")
def get_crop_prices() -> Dict[str, Any]:
    return {
        "currency": "INR",
        "prices_inr_per_tonne": CROP_PRICES_INR_PER_TONNE,
    }


@app.get("/location/context")
def location_context(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> Dict[str, Any]:
    try:
        return get_location_context(latitude, longitude, yield_options.get("areas", []))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch location data: {exc}") from exc


def estimate_crop_price_inr(crop_name: str) -> float:
    normalized = crop_name.lower().strip()
    if normalized in CROP_PRICES_INR_PER_TONNE:
        return CROP_PRICES_INR_PER_TONNE[normalized]

    for key, value in CROP_PRICES_INR_PER_TONNE.items():
        if key in normalized or normalized in key:
            return value

    return CROP_PRICES_INR_PER_TONNE["default"]


@app.post("/dashboard/profit", response_model=ProfitResponse)
def calculate_profit(payload: ProfitRequest) -> ProfitResponse:
    pesticide_cost = payload.pesticide_spend or (payload.farm_area_ha * 4500)
    total_costs = (
        pesticide_cost
        + payload.seed_cost
        + payload.labor_cost
        + payload.fertilizer_cost
    )
    revenue = payload.predicted_tonnes * payload.market_price_per_tonne
    net_profit = revenue - total_costs
    profit_per_hectare = net_profit / payload.farm_area_ha
    margin_percent = (net_profit / revenue * 100) if revenue else 0

    return ProfitResponse(
        revenue=round(revenue, 2),
        total_costs=round(total_costs, 2),
        net_profit=round(net_profit, 2),
        profit_per_hectare=round(profit_per_hectare, 2),
        margin_percent=round(margin_percent, 2),
        breakdown={
            "pesticide_cost": round(pesticide_cost, 2),
            "seed_cost": round(payload.seed_cost, 2),
            "labor_cost": round(payload.labor_cost, 2),
            "fertilizer_cost": round(payload.fertilizer_cost, 2),
        },
    )


@app.get("/dashboard/records")
def get_user_dashboard_records(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    records = list_dashboard_records(user["id"])
    return {"currency": "INR", "records": records}


@app.post("/dashboard/records")
def save_user_dashboard_record(
    payload: DashboardRecordRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    record = add_dashboard_record(
        user["id"],
        {
            "crop": payload.crop,
            "region": payload.region,
            "production_tonnes": payload.production_tonnes,
            "revenue": payload.revenue,
            "costs": payload.costs,
            "profit": payload.profit,
            "margin": payload.margin,
            "data_json": payload.data_json,
        },
    )
    return {"message": "Record saved.", "record": record}


@app.delete("/dashboard/records")
def delete_user_dashboard_records(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, str]:
    clear_dashboard_records(user["id"])
    return {"message": "Dashboard history cleared."}


@app.get("/predict/pests")
def predict_pests(crop: str = Query(..., min_length=1)) -> Dict[str, Any]:
    return get_pest_prediction(crop)


@app.post("/alerts/subscribe")
def subscribe_alerts(
    payload: AlertSubscribeRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    subscription = upsert_alert_subscription(
        user["id"],
        payload.crop,
        payload.latitude,
        payload.longitude,
    )
    return {"message": "Emergency crop alerts enabled.", "subscription": subscription}


@app.post("/alerts/check")
def check_alerts(
    payload: AlertSubscribeRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    upsert_alert_subscription(user["id"], payload.crop, payload.latitude, payload.longitude)
    result = check_and_notify_user(user, payload.crop, payload.latitude, payload.longitude)
    return result


@app.get("/alerts/history")
def alert_history(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"alerts": list_alert_logs(user["id"])}


@app.post("/predict/crop", response_model=CropPredictionResponse)
def predict_crop(payload: CropPredictionRequest) -> CropPredictionResponse:
    ensure_models_loaded()

    feature_names = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
    input_df = pd.DataFrame([payload.model_dump()], columns=feature_names)

    try:
        recommended = str(crop_model.predict(input_df)[0])
        top_predictions: List[CropCandidate] = []

        if hasattr(crop_model, "predict_proba"):
            probabilities = crop_model.predict_proba(input_df)[0]
            classes = crop_model.classes_
            ranked = sorted(
                zip(classes, probabilities), key=lambda item: item[1], reverse=True
            )
            top_predictions = [
                CropCandidate(crop=str(crop), confidence=round(float(prob) * 100, 2))
                for crop, prob in ranked[:3]
            ]

        return CropPredictionResponse(
            recommended_crop=recommended,
            top_predictions=top_predictions,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crop prediction failed: {exc}") from exc


@app.post("/predict/yield", response_model=YieldPredictionResponse)
def predict_yield(payload: YieldPredictionRequest) -> YieldPredictionResponse:
    ensure_models_loaded()

    model_input = {
        "Area": payload.Area,
        "Item": payload.Item,
        "Year": payload.Year,
        "avg_temp": payload.avg_temp,
        "average_rain_fall_mm_per_year": payload.average_rain_fall_mm_per_year,
        "pesticides_tonnes": payload.pesticides_tonnes,
    }
    input_df = pd.DataFrame([model_input])

    try:
        predicted_hg_ha = float(yield_model.predict(input_df)[0])
        predicted_total_tonnes = (predicted_hg_ha * payload.farm_area_ha) / 10_000

        return YieldPredictionResponse(
            predicted_hg_ha_yield=round(predicted_hg_ha, 2),
            predicted_total_tonnes=round(predicted_total_tonnes, 2),
            farm_area_ha=payload.farm_area_ha,
            input_data=payload,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Yield prediction failed: {exc}") from exc


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css", include_in_schema=False)
def serve_style() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/script.js", include_in_schema=False)
def serve_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "script.js")
