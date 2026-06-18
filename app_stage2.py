import csv, json, requests
from datetime import datetime
from pathlib import Path

ALPHA_VANTAGE_API_KEY = "B2ATNTCJ5MQCGT68"
CITY = "Delhi"
TARGET_CURRENCY = "INR"
DATA_DIR = Path("data")

def get_crude_oil_price():
    url = "https://www.alphavantage.co/query"
    params = {"function": "WTI", "interval": "daily", "apikey": ALPHA_VANTAGE_API_KEY}
    data = requests.get(url, params=params, timeout=10).json()
    try:
        return float(data["data"][0]["value"])
    except (KeyError, IndexError, ValueError, TypeError):
        print("Oil price fetch failed:", data); return None

def get_usd_exchange_rate(target_currency=TARGET_CURRENCY):
    data = requests.get("https://api.frankfurter.app/latest",
                        params={"from": "USD", "to": target_currency}, timeout=10).json()
    try:
        return data["rates"][target_currency]
    except (KeyError, TypeError):
        print("Rate fetch failed:", data); return None

def get_weather(city=CITY):
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1}, timeout=10).json()
    if not geo.get("results"):
        print(f"City not found: {city}"); return None
    lat, lon = geo["results"][0]["latitude"], geo["results"][0]["longitude"]
    w = requests.get("https://api.open-meteo.com/v1/forecast",
                     params={"latitude": lat, "longitude": lon, "current_weather": True}, timeout=10).json()
    try:
        cw = w["current_weather"]
        return {"city": city, "temperature_c": cw["temperature"], "windspeed_kph": cw["windspeed"]}
    except (KeyError, TypeError):
        print("Weather parse failed:", w); return None

def save_snapshot(record):
    DATA_DIR.mkdir(exist_ok=True)
    safe_ts = record["timestamp"].replace(":", "-").replace(" ", "_")
    path = DATA_DIR / f"snapshot_{safe_ts}.json"
    path.write_text(json.dumps(record, indent=2))
    print(f"  Snapshot saved -> {path}")

def append_to_log(record):
    DATA_DIR.mkdir(exist_ok=True)
    log_path = DATA_DIR / "log.csv"
    col = f"usd_to_{TARGET_CURRENCY.lower()}"
    headers = ["timestamp", "oil_usd_per_barrel", col, "city", "temperature_c", "windspeed_kph"]
    write_header = not log_path.exists()
    with open(log_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if write_header:
            writer.writeheader()
        wx = record.get("weather") or {}
        writer.writerow({
            "timestamp": record["timestamp"],
            "oil_usd_per_barrel": record["oil_usd_per_barrel"],
            col: record["usd_to_inr"],
            "city": wx.get("city", ""),
            "temperature_c": wx.get("temperature_c", ""),
            "windspeed_kph": wx.get("windspeed_kph", ""),
        })
    print(f"  Row appended  -> {log_path}")

def fetch_all():
    print("\n--- Fetching ---")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    oil = get_crude_oil_price()
    rate = get_usd_exchange_rate()
    weather = get_weather()
    record = {"timestamp": timestamp, "oil_usd_per_barrel": oil, "usd_to_inr": rate, "weather": weather}
    print("\n--- Saving ---")
    save_snapshot(record)
    append_to_log(record)
    print(f"\n  Time       : {timestamp}")
    print(f"  Crude Oil  : {oil} USD/barrel")
    print(f"  USD -> INR : {rate}")
    if weather:
        print(f"  Weather    : {weather['temperature_c']}C  wind {weather['windspeed_kph']} kph  {weather['city']}")
    return record

if __name__ == "__main__":
    fetch_all()