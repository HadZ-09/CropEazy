import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


def send_sms(phone: str, message: str) -> dict:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if account_sid and auth_token and from_number:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = urllib.parse.urlencode(
            {"To": phone, "From": from_number, "Body": message}
        ).encode()
        request = urllib.request.Request(url, data=payload, method="POST")
        credentials = f"{account_sid}:{auth_token}".encode()
        import base64

        request.add_header(
            "Authorization",
            "Basic " + base64.b64encode(credentials).decode(),
        )
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return {"sent": True, "provider": "twilio", "detail": response.read().decode()}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            if dev_mode:
                print(f"[DEV SMS -> {phone}] {message}")
                return {"sent": True, "provider": "dev-fallback", "detail": body}
            raise RuntimeError(f"Twilio SMS failed: {body}") from exc

    if dev_mode:
        print(f"[DEV SMS -> {phone}] {message}")
        return {"sent": True, "provider": "dev", "detail": "SMS logged in development mode."}

    raise RuntimeError(
        "SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
    )


def send_otp_sms(phone: str, otp: str) -> dict:
    message = f"Your CropEazy OTP is {otp}. Valid for 5 minutes. Do not share this code."
    return send_sms(phone, message)
