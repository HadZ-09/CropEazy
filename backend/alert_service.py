import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from backend.database import add_alert_log
from backend.sms_service import send_sms


def fetch_weather_alerts(latitude: float, longitude: float) -> List[Dict[str, Any]]:
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
                "forecast_days": 3,
                "timezone": "auto",
            }
        )
    )

    with urllib.request.urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode())

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    alerts: List[Dict[str, Any]] = []

    for index, day in enumerate(dates):
        rain = (daily.get("precipitation_sum") or [0])[index]
        temp = (daily.get("temperature_2m_max") or [0])[index]
        wind = (daily.get("wind_speed_10m_max") or [0])[index]

        if rain >= 80:
            alerts.append(
                {
                    "type": "flood",
                    "severity": "high",
                    "date": day,
                    "message": f"Heavy rainfall alert ({rain:.0f} mm) expected on {day}. Protect standing crops and improve drainage.",
                }
            )
        elif rain >= 45:
            alerts.append(
                {
                    "type": "heavy_rain",
                    "severity": "medium",
                    "date": day,
                    "message": f"Moderate to heavy rain ({rain:.0f} mm) expected on {day}. Delay pesticide spraying.",
                }
            )

        if temp >= 42:
            alerts.append(
                {
                    "type": "heatwave",
                    "severity": "high",
                    "date": day,
                    "message": f"Heatwave alert ({temp:.1f}°C) on {day}. Increase irrigation for sensitive crops.",
                }
            )

        if wind >= 45:
            alerts.append(
                {
                    "type": "storm",
                    "severity": "high",
                    "date": day,
                    "message": f"Strong wind alert ({wind:.0f} km/h) on {day}. Secure trellises and harvest-ready produce.",
                }
            )

    return alerts


def check_and_notify_user(
    user: Dict[str, Any],
    crop: str,
    latitude: Optional[float],
    longitude: Optional[float],
) -> Dict[str, Any]:
    if latitude is None or longitude is None:
        return {"alerts": [], "sms_sent": False, "message": "Location required for calamity alerts."}

    alerts = fetch_weather_alerts(latitude, longitude)
    high_alerts = [alert for alert in alerts if alert["severity"] == "high"]

    sms_sent = False
    if high_alerts:
        headline = high_alerts[0]["message"]
        sms_body = (
            f"CropEazy Emergency Alert for your {crop} crop: {headline} "
            "Open the app for full advisory."
        )
        send_sms(user["phone"], sms_body)
        add_alert_log(user["id"], sms_body, high_alerts[0]["type"])
        sms_sent = True

    return {
        "alerts": alerts,
        "sms_sent": sms_sent,
        "message": "Emergency SMS sent." if sms_sent else "No high-severity alerts right now.",
    }
