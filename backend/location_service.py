import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from difflib import get_close_matches
from typing import Any, Dict, List, Optional


def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "CropEazy/1.0 (crop intelligence app)"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def match_area_name(country: str, known_areas: List[str]) -> str:
    if not country:
        return known_areas[0] if known_areas else "India"

    if country in known_areas:
        return country

    lowered = country.lower()
    for area in known_areas:
        if area.lower() == lowered:
            return area

    close = get_close_matches(country, known_areas, n=1, cutoff=0.6)
    if close:
        return close[0]

    for area in known_areas:
        if lowered in area.lower() or area.lower() in lowered:
            return area

    return country


def get_location_context(
    latitude: float,
    longitude: float,
    known_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    known_areas = known_areas or []

    reverse_url = (
        "https://nominatim.openstreetmap.org/reverse?"
        + urllib.parse.urlencode(
            {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1,
            }
        )
    )
    place = _fetch_json(reverse_url)
    address = place.get("address", {})

    country = address.get("country", "")
    region = address.get("state") or address.get("region") or address.get("county") or ""
    city = address.get("city") or address.get("town") or address.get("village") or ""
    matched_area = match_area_name(country, known_areas)

    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    weather_url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,precipitation",
                "timezone": "auto",
            }
        )
    )
    weather = _fetch_json(weather_url)
    current = weather.get("current", {})

    archive_url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        + urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": "precipitation_sum,temperature_2m_mean,relative_humidity_2m_mean",
                "timezone": "auto",
            }
        )
    )

    try:
        archive = _fetch_json(archive_url)
        daily = archive.get("daily", {})
        precipitation = daily.get("precipitation_sum") or []
        temperatures = daily.get("temperature_2m_mean") or []
        humidities = daily.get("relative_humidity_2m_mean") or []

        annual_rainfall = round(sum(precipitation), 1) if precipitation else None
        avg_temp = round(sum(temperatures) / len(temperatures), 1) if temperatures else None
        avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else None
    except (urllib.error.URLError, KeyError, ZeroDivisionError):
        annual_rainfall = None
        avg_temp = None
        avg_humidity = None

    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")

    return {
        "latitude": latitude,
        "longitude": longitude,
        "display_name": place.get("display_name", ""),
        "country": country,
        "region": region,
        "city": city,
        "matched_area": matched_area,
        "temperature": round(float(temperature), 1) if temperature is not None else avg_temp,
        "humidity": round(float(humidity), 1) if humidity is not None else avg_humidity,
        "avg_temp": avg_temp or (round(float(temperature), 1) if temperature is not None else None),
        "annual_rainfall_mm": annual_rainfall,
        "monthly_rainfall_mm": round(annual_rainfall / 12, 1) if annual_rainfall else None,
        "year": date.today().year,
    }
