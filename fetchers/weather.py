import requests
from config.settings import CITY, OPENWEATHER_API_KEY
from core.errors import FETCH_ERRORS, classify_request_error


def get_weather(city: str = CITY) -> dict | None:
    FETCH_ERRORS["weather"] = None

    if not OPENWEATHER_API_KEY:
        FETCH_ERRORS["weather"] = "API key missing — check .env file"
        return None

    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "city":         city,
            "temp_c":       data["main"]["temp"],
            "feels_like_c": data["main"]["feels_like"],
            "humidity_pct": data["main"]["humidity"],
            "description":  data["weather"][0]["description"],
            "wind_kph":     round(data["wind"]["speed"] * 3.6, 1),
        }

    except requests.exceptions.HTTPError as exc:
        reason = classify_request_error(exc)
        code   = getattr(exc.response, "status_code", 0)
        if code == 401:
            reason = "Invalid API key (new keys take up to 2 hrs)"
        elif code == 404:
            reason = f"City '{city}' not found"
        FETCH_ERRORS["weather"] = reason
        return None

    except requests.exceptions.RequestException as exc:
        FETCH_ERRORS["weather"] = classify_request_error(exc)
        return None

    except Exception as exc:
        FETCH_ERRORS["weather"] = f"Error: {str(exc)[:60]}"
        return None