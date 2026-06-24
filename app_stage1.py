"""
STAGE 1 (v2): Data Fetchers — with specific error reporting
------------------------------------------------------------
Each function now returns either:
  • the real value on success
  • None on failure

AND populates FETCH_ERRORS[source] with a short human-readable reason
so the GUI can show WHY something failed, not just that it did.

SOURCES DICT is also exported so the GUI can display source labels.
"""

import yfinance as yf
import requests

# ── CONFIG ────────────────────────────────────────────────────────────────────
CITY                = "Delhi"
OPENWEATHER_API_KEY = "e04c14e1857cc5380c0b0170a08e95dc"

# ── ERROR STORE ───────────────────────────────────────────────────────────────
# A shared dictionary that each fetcher writes to when something goes wrong.
# The GUI imports this to know WHAT failed, not just that it did.
# Keys: "oil" | "fx" | "weather"
# Values: short human-readable string, or None if the last fetch succeeded.
FETCH_ERRORS: dict = {"oil": None, "fx": None, "weather": None}


# ── HELPER: classify network errors ──────────────────────────────────────────
def _classify_request_error(exc) -> str:
    """
    Turns a requests exception into a short label the GUI can display.
    ConnectionError   → user is offline or DNS failed
    Timeout           → server too slow
    HTTPError 401     → wrong API key
    HTTPError 429     → too many requests (rate limited)
    HTTPError 5xx     → server-side problem
    """
    msg = str(exc).lower()
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "No internet connection"
    if isinstance(exc, requests.exceptions.Timeout):
        return "Connection timed out"
    if isinstance(exc, requests.exceptions.HTTPError):
        code = getattr(exc.response, "status_code", 0)
        if code == 401: return "Invalid API key (401)"
        if code == 429: return "Rate limited — try later (429)"
        if code >= 500: return f"Server error ({code})"
        return f"HTTP error ({code})"
    return "Unknown network error"


# ── FUNCTION 1: Crude oil ─────────────────────────────────────────────────────
def get_crude_oil_price():
    """
    Returns the WTI crude oil price in USD/barrel, or None on failure.
    Uses fast_info['last_price'] for the live quote.
    Falls back to the most recent 1-minute intraday bar if fast_info is empty.
    """
    FETCH_ERRORS["oil"] = None   # clear any previous error

    try:
        ticker  = yf.Ticker("CL=F")

        # PRIMARY: live quote
        price = ticker.fast_info.get("last_price") or ticker.fast_info.get("lastPrice")
        if price and float(price) > 0:
            return round(float(price), 2)

        # FALLBACK: most recent minute bar
        intraday = ticker.history(period="1d", interval="1m")
        if not intraday.empty:
            return round(float(intraday["Close"].iloc[-1]), 2)

        # If both returned nothing, markets are almost certainly closed
        FETCH_ERRORS["oil"] = "Markets closed / no data"
        return None

    except Exception as exc:
        err = str(exc)
        # yfinance wraps network failures; look for the telltale signs
        if "connection" in err.lower() or "network" in err.lower() or "failed to get" in err.lower():
            FETCH_ERRORS["oil"] = "No internet connection"
        elif "json" in err.lower():
            FETCH_ERRORS["oil"] = "Bad data from Yahoo Finance"
        else:
            FETCH_ERRORS["oil"] = f"Error: {err[:60]}"
        return None


# ── FUNCTION 2: USD → INR rate ────────────────────────────────────────────────
def get_usd_inr_rate():
    """
    Returns how many INR one USD buys, or None on failure.
    USDINR=X is the Yahoo Finance ticker for the USD/INR forex pair.
    Forex runs almost 24/7 so "markets closed" is rarely the cause here.
    """
    FETCH_ERRORS["fx"] = None

    try:
        ticker   = yf.Ticker("USDINR=X")

        price = ticker.fast_info.get("last_price") or ticker.fast_info.get("lastPrice")
        if price and float(price) > 0:
            return round(float(price), 4)

        intraday = ticker.history(period="1d", interval="1m")
        if not intraday.empty:
            return round(float(intraday["Close"].iloc[-1]), 4)

        FETCH_ERRORS["fx"] = "Markets closed / no data"
        return None

    except Exception as exc:
        err = str(exc)
        if "connection" in err.lower() or "network" in err.lower() or "failed to get" in err.lower():
            FETCH_ERRORS["fx"] = "No internet connection"
        elif "json" in err.lower():
            FETCH_ERRORS["fx"] = "Bad data from Yahoo Finance"
        else:
            FETCH_ERRORS["fx"] = f"Error: {err[:60]}"
        return None


# ── FUNCTION 3: Weather ───────────────────────────────────────────────────────
def get_weather(city=CITY):
    """
    Returns a weather dict, or None on failure.
    OpenWeatherMap error codes:
      401 → API key wrong or not yet activated (new keys take up to 2 hours)
      404 → city name not found
      429 → free-tier rate limit hit
    """
    FETCH_ERRORS["weather"] = None

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q":     city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }
        response = requests.get(url, params=params, timeout=10)
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
        FETCH_ERRORS["weather"] = _classify_request_error(exc)
        if "401" in FETCH_ERRORS["weather"]:
            FETCH_ERRORS["weather"] = "Invalid API key (new keys take up to 2 hrs)"
        if "404" in str(exc):
            FETCH_ERRORS["weather"] = f"City '{city}' not found"
        return None

    except requests.exceptions.RequestException as exc:
        FETCH_ERRORS["weather"] = _classify_request_error(exc)
        return None

    except Exception as exc:
        FETCH_ERRORS["weather"] = f"Error: {str(exc)[:60]}"
        return None


# ── QUICK TEST ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 45)
    print("  FETCHING LIVE DATA")
    print("=" * 45)

    print("\n📦 Crude Oil (WTI)...")
    oil = get_crude_oil_price()
    if oil:
        print(f"   ${oil} USD / barrel")
    else:
        print(f"   Failed: {FETCH_ERRORS['oil']}")

    print("\n💵 USD → INR Rate...")
    rate = get_usd_inr_rate()
    if rate:
        print(f"   1 USD = ₹{rate}")
    else:
        print(f"   Failed: {FETCH_ERRORS['fx']}")

    print(f"\n🌤  Weather in {CITY}...")
    weather = get_weather()
    if weather:
        print(f"   {weather['temp_c']}°C  |  {weather['description'].capitalize()}")
        print(f"   Humidity: {weather['humidity_pct']}%  |  Wind: {weather['wind_kph']} kph")
    else:
        print(f"   Failed: {FETCH_ERRORS['weather']}")

    print("\n" + "=" * 45)