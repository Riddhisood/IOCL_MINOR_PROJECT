import json
import csv
import os
from datetime import datetime

from config.settings import DATA_FOLDER, CSV_FILE, CSV_HEADERS

def ensure_folder():
    os.makedirs(DATA_FOLDER, exist_ok=True)


def _save_json(result: dict, timestamp_file: str) -> str:
    filepath = os.path.join(DATA_FOLDER, f"snapshot_{timestamp_file}.json")
    with open(filepath, "w") as f:
        json.dump(result, f, indent=2)
    return filepath


def _save_csv_row(result: dict):
    weather = result.get("weather") or {}
    row = {
        "timestamp":          result["timestamp"],
        "oil_usd_per_barrel": result["oil_usd_per_barrel"],
        "usd_inr_rate":       result["usd_inr_rate"],
        "city":               weather.get("city", ""),
        "temp_c":             weather.get("temp_c", ""),
        "feels_like_c":       weather.get("feels_like_c", ""),
        "humidity_pct":       weather.get("humidity_pct", ""),
        "description":        weather.get("description", ""),
        "wind_kph":           weather.get("wind_kph", ""),
    }
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def fetch_and_save() -> dict:
    from fetchers.oil     import get_crude_oil_price
    from fetchers.forex   import get_usd_inr_rate
    from fetchers.weather import get_weather

    ensure_folder()

    now            = datetime.now()
    timestamp_str  = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")

    result = {
        "timestamp":          timestamp_str,
        "oil_usd_per_barrel": get_crude_oil_price(),
        "usd_inr_rate":       get_usd_inr_rate(),
        "weather":            get_weather(),
    }

    _save_json(result, timestamp_file)
    _save_csv_row(result)

    return result