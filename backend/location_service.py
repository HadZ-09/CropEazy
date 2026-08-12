import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from difflib import get_close_matches
from typing import Any, Callable, Dict, List, Optional, Tuple

USER_AGENT = "CropEazy/1.0 (https://github.com/HadZ-09/CropEazy)"
CACHE_TTL_SECONDS = 86400
_location_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# OpenWeatherMap returns ISO country codes — map common ones to yield-dataset country names.
ISO_COUNTRY_NAMES: Dict[str, str] = {
    "IN": "India",
    "US": "United States of America",
    "GB": "United Kingdom",
    "CN": "China",
    "BR": "Brazil",
    "AU": "Australia",
    "CA": "Canada",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "MX": "Mexico",
    "AR": "Argentina",
    "ZA": "South Africa",
    "NG": "Nigeria",
    "EG": "Egypt",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "ID": "Indonesia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "MY": "Malaysia",
    "JP": "Japan",
    "KR": "Korea, Republic of",
    "RU": "Russian Federation",
    "TR": "Turkey",
    "PL": "Poland",
    "NL": "Netherlands",
    "BE": "Belgium",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "CH": "Switzerland",
    "AT": "Austria",
    "PT": "Portugal",
    "GR": "Greece",
    "IE": "Ireland",
    "NZ": "New Zealand",
    "KE": "Kenya",
    "ET": "Ethiopia",
    "CO": "Colombia",
    "PE": "Peru",
    "CL": "Chile",
    "UA": "Ukraine",
    "RO": "Romania",
    "HU": "Hungary",
    "CZ": "Czech Republic",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "IL": "Israel",
    "IR": "Iran",
    "IQ": "Iraq",
}


def _openweather_key() -> Optional[str]:
    key = (os.getenv("OPENWEATHER_API_KEY") or os.getenv("OWM_API_KEY") or "").strip()
    return key or None


def _country_name(code_or_name: str) -> str:
    value = (code_or_name or "").strip()
    if len(value) == 2:
        return ISO_COUNTRY_NAMES.get(value.upper(), value)
    return value


def _cache_key(latitude: float, longitude: float) -> str:
    return f"{round(latitude, 3)},{round(longitude, 3)}"


def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def _fetch_json_safe(url: str) -> Optional[Any]:
    try:
        return _fetch_json(url)
    except urllib.error.HTTPError as exc:
        print(f"Location API HTTP {exc.code}: {url[:100]}")
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Location API error: {exc} — {url[:100]}")
        return None


def match_area_name(country: str, known_areas: List[str]) -> str:
    country = _country_name(country)
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


def _reverse_geocode_openweather(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    api_key = _openweather_key()
    if not api_key:
        return None

    url = (
        "https://api.openweathermap.org/geo/1.0/reverse?"
        + urllib.parse.urlencode(
            {
                "lat": latitude,
                "lon": longitude,
                "limit": 1,
                "appid": api_key,
            }
        )
    )
    data = _fetch_json_safe(url)
    if not data or not isinstance(data, list) or not data:
        return None

    item = data[0]
    city = item.get("name", "")
    region = item.get("state", "")
    country = _country_name(item.get("country", ""))
    return {
        "display_name": ", ".join(part for part in [city, region, country] if part),
        "country": country,
        "region": region,
        "city": city,
    }


def _reverse_geocode_nominatim(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
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
    place = _fetch_json_safe(reverse_url)
    if not place:
        return None

    address = place.get("address", {})
    return {
        "display_name": place.get("display_name", ""),
        "country": address.get("country", ""),
        "region": address.get("state") or address.get("region") or address.get("county") or "",
        "city": address.get("city") or address.get("town") or address.get("village") or "",
    }


def _reverse_geocode_bigdatacloud(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    url = (
        "https://api.bigdatacloud.net/data/reverse-geocode-client?"
        + urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "localityLanguage": "en",
            }
        )
    )
    place = _fetch_json_safe(url)
    if not place:
        return None

    city = (
        place.get("city")
        or place.get("locality")
        or (place.get("localityInfo", {}).get("administrative") or [{}])[0].get("name", "")
    )
    return {
        "display_name": ", ".join(
            part
            for part in [city, place.get("principalSubdivision"), place.get("countryName")]
            if part
        ),
        "country": place.get("countryName", ""),
        "region": place.get("principalSubdivision", ""),
        "city": city or "",
    }


def _reverse_geocode(latitude: float, longitude: float) -> Dict[str, Any]:
    on_cloud = bool(
        os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("VERCEL")
    )

    if _openweather_key():
        providers: Tuple[Callable[[float, float], Optional[Dict[str, Any]]], ...] = (
            _reverse_geocode_openweather,
            _reverse_geocode_bigdatacloud,
        )
    elif on_cloud:
        providers = (_reverse_geocode_bigdatacloud, _reverse_geocode_nominatim)
    else:
        providers = (_reverse_geocode_nominatim, _reverse_geocode_bigdatacloud)

    for provider in providers:
        place = provider(latitude, longitude)
        if place and (place.get("country") or place.get("city")):
            return place

    return {
        "display_name": f"{latitude:.4f}, {longitude:.4f}",
        "country": "India",
        "region": "",
        "city": "",
    }


def _empty_weather() -> Dict[str, Any]:
    return {
        "temperature": None,
        "humidity": None,
        "avg_temp": None,
        "annual_rainfall_mm": None,
        "monthly_rainfall_mm": None,
        "year": date.today().year,
        "weather_provider": "none",
    }


def _fetch_rainfall_open_meteo(latitude: float, longitude: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    # Archive API lags ~5 days — requesting "today" returns HTTP 400.
    end_date = date.today() - timedelta(days=5)
    start_date = end_date - timedelta(days=365)
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
    archive = _fetch_json_safe(archive_url)
    if not archive:
        return None, None, None

    daily = archive.get("daily", {})
    precipitation = daily.get("precipitation_sum") or []
    temperatures = daily.get("temperature_2m_mean") or []
    humidities = daily.get("relative_humidity_2m_mean") or []

    annual_rainfall = round(sum(precipitation), 1) if precipitation else None
    avg_temp = round(sum(temperatures) / len(temperatures), 1) if temperatures else None
    avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else None
    return annual_rainfall, avg_temp, avg_humidity


def _fetch_weather_openweather(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    api_key = _openweather_key()
    if not api_key:
        return None

    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        + urllib.parse.urlencode(
            {
                "lat": latitude,
                "lon": longitude,
                "appid": api_key,
                "units": "metric",
            }
        )
    )
    data = _fetch_json_safe(url)
    if not data:
        return None

    main = data.get("main", {})
    temperature = main.get("temp")
    humidity = main.get("humidity")
    annual_rainfall, avg_temp, avg_humidity = _fetch_rainfall_open_meteo(latitude, longitude)

    temp_value = round(float(temperature), 1) if temperature is not None else avg_temp
    humidity_value = round(float(humidity), 1) if humidity is not None else avg_humidity

    return {
        "temperature": temp_value,
        "humidity": humidity_value,
        "avg_temp": avg_temp or temp_value,
        "annual_rainfall_mm": annual_rainfall,
        "monthly_rainfall_mm": round(annual_rainfall / 12, 1) if annual_rainfall else None,
        "year": date.today().year,
        "weather_provider": "openweathermap",
    }


def _fetch_weather_open_meteo(latitude: float, longitude: float) -> Dict[str, Any]:
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
    weather = _fetch_json_safe(weather_url)
    if not weather:
        return _empty_weather()

    current = weather.get("current", {})
    annual_rainfall, avg_temp, avg_humidity = _fetch_rainfall_open_meteo(latitude, longitude)

    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")

    return {
        "temperature": round(float(temperature), 1) if temperature is not None else avg_temp,
        "humidity": round(float(humidity), 1) if humidity is not None else avg_humidity,
        "avg_temp": avg_temp or (round(float(temperature), 1) if temperature is not None else None),
        "annual_rainfall_mm": annual_rainfall,
        "monthly_rainfall_mm": round(annual_rainfall / 12, 1) if annual_rainfall else None,
        "year": date.today().year,
        "weather_provider": "open-meteo",
    }


def _fetch_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    if _openweather_key():
        weather = _fetch_weather_openweather(latitude, longitude)
        if weather:
            return weather

    return _fetch_weather_open_meteo(latitude, longitude)


def get_location_context(
    latitude: float,
    longitude: float,
    known_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    known_areas = known_areas or []
    key = _cache_key(latitude, longitude)
    cached = _location_cache.get(key)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    place = _reverse_geocode(latitude, longitude)
    weather = _fetch_weather(latitude, longitude)
    matched_area = match_area_name(place.get("country", ""), known_areas)

    result = {
        "latitude": latitude,
        "longitude": longitude,
        "display_name": place.get("display_name", ""),
        "country": place.get("country", ""),
        "region": place.get("region", ""),
        "city": place.get("city", ""),
        "matched_area": matched_area,
        **weather,
    }

    _location_cache[key] = (time.time(), result)
    return result
