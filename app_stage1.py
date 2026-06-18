"""
STAGE 1: Data Fetchers
-----------------------
This file defines three small functions. Each one has exactly ONE job:
talk to a web API and hand back a clean Python value.

  1. get_crude_oil_price()    -> talks to Alpha Vantage
  2. get_usd_exchange_rate()  -> talks to Frankfurter
  3. get_weather()            -> talks to Open-Meteo (two steps: city -> coordinates -> weather)

Run this file directly:
    python3 app_stage1.py

You should see three results print to your terminal. There's no
saving and no window yet - that comes in later stages. The goal of
Stage 1 is just: "can my computer successfully ask the internet for
data and understand the answer?"
"""

import requests

# ---- CONFIG: things you'll likely want to change ----
ALPHA_VANTAGE_API_KEY = "B2ATNTCJ5MQCGT68"  # free key: alphavantage.co/support/#api-key
CITY = "Delhi"
TARGET_CURRENCY = "INR"  # we'll check how many of these one US dollar buys


def get_crude_oil_price():
    """Return the latest WTI crude oil price in USD per barrel, or None if something went wrong."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "WTI",
        "interval": "daily",
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()  # .json() turns the raw text reply into a Python dict

    try:
        latest_entry = data["data"][0]  # the API returns a list of {date, value}, newest first
        return float(latest_entry["value"])
    except (KeyError, IndexError, ValueError, TypeError):
        print("Couldn't read the oil price. Here's what the API actually sent back:")
        print(data)
        return None


def get_usd_exchange_rate(target_currency=TARGET_CURRENCY):
    """Return how many units of target_currency one US dollar buys right now."""
    url = "https://api.frankfurter.app/latest"
    params = {"from": "USD", "to": target_currency}
    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    try:
        return data["rates"][target_currency]
    except (KeyError, TypeError):
        print("Couldn't read the exchange rate. Here's what the API actually sent back:")
        print(data)
        return None


def get_weather(city=CITY):
    """Return a small dict with temperature and wind speed for `city`."""
    # Step A: turn a city name like "Delhi" into latitude/longitude
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_response = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10)
    geo_data = geo_response.json()

    if not geo_data.get("results"):
        print(f"Couldn't find a location named '{city}'.")
        return None

    location = geo_data["results"][0]
    lat, lon = location["latitude"], location["longitude"]

    # Step B: use those coordinates to ask for the current weather
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_response = requests.get(
        weather_url,
        params={"latitude": lat, "longitude": lon, "current_weather": True},
        timeout=10,
    )
    weather_data = weather_response.json()

    try:
        current = weather_data["current_weather"]
        return {
            "city": city,
            "temperature_c": current["temperature"],
            "windspeed_kph": current["windspeed"],
        }
    except (KeyError, TypeError):
        print("Couldn't read the weather. Here's what the API actually sent back:")
        print(weather_data)
        return None


if __name__ == "__main__":
    print("Fetching crude oil price...")
    print(" ->", get_crude_oil_price(), "USD per barrel\n")

    print(f"Fetching USD -> {TARGET_CURRENCY} exchange rate...")
    print(" ->", get_usd_exchange_rate(), "\n")

    print(f"Fetching weather for {CITY}...")
    print(" ->", get_weather())
