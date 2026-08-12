import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Header

from backend.database import (
    create_user,
    delete_otp,
    get_otp,
    get_user_by_id,
    get_user_by_phone,
    save_otp,
)
from backend.sms_service import send_otp_sms

JWT_SECRET = os.getenv("JWT_SECRET", "cropeazy-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return f"+91{digits}"
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if phone.startswith("+") and len(digits) >= 10:
        return f"+{digits}"
    raise ValueError("Enter a valid 10-digit Indian mobile number.")


def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"


def create_access_token(user_id: str, phone: str) -> str:
    payload = {
        "sub": user_id,
        "phone": phone,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required.")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


def send_login_otp(phone: str) -> Dict[str, Any]:
    normalized = normalize_phone(phone)
    code = generate_otp()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    save_otp(normalized, code, expires_at)
    sms_result = send_otp_sms(normalized, code)

    response = {
        "message": "OTP sent to your mobile number.",
        "phone": normalized,
        "provider": sms_result.get("provider"),
    }
    if DEV_MODE:
        response["dev_otp"] = code
    return response


def verify_login_otp(phone: str, otp: str, name: str = "") -> Dict[str, Any]:
    normalized = normalize_phone(phone)
    stored = get_otp(normalized)
    if not stored:
        raise HTTPException(status_code=400, detail="OTP expired or not requested.")

    expires_at = datetime.fromisoformat(stored["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        delete_otp(normalized)
        raise HTTPException(status_code=400, detail="OTP has expired. Request a new one.")

    if stored["code"] != otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    delete_otp(normalized)
    user = get_user_by_phone(normalized)
    if not user:
        user = create_user(normalized, name or "Farmer")

    token = create_access_token(user["id"], user["phone"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "phone": user["phone"], "name": user["name"]},
    }
