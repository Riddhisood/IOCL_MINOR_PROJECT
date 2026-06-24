"""
STAGE 2: Timestamps + Saving to Disk
--------------------------------------
Builds on Stage 1 by adding:

  1. TIMESTAMP  — every fetch is tagged with the exact date & time
  2. SAVING     — results go into  data_logs/  as:
       • a JSON snapshot  →  one file per fetch, named by timestamp
       • a CSV log row    →  one line appended to a running log file

FOLDER STRUCTURE (created automatically next to this script):
  IOCL_MINOR_PROJECT/
  └── data_logs/
      ├── snapshot_2026-06-24_14-30-00.json   ← full detail, one per click
      ├── snapshot_2026-06-24_15-00-00.json
      └── running_log.csv                      ← all fetches in one table

Run to test:
    python3 app_stage2.py
"""

import json
import csv
import os
from datetime import datetime

# Borrow the three fetcher functions we built in Stage 1.
# Python treats each .py file as a "module" you can import from.
from app_stage1 import get_crude_oil_price, get_usd_inr_rate, get_weather, CITY


# ── CONFIG ────────────────────────────────────────────────────────────────────
# Path is relative — so data_logs/ appears right inside your project folder.
DATA_FOLDER = "data_logs"
CSV_FILE    = os.path.join(DATA_FOLDER, "running_log.csv")

CSV_HEADERS = [
    "timestamp",
    "oil_usd_per_barrel",
    "usd_inr_rate",
    "city",
    "temp_c",
    "feels_like_c",
    "humidity_pct",
    "description",
    "wind_kph",
]


# ── HELPER ────────────────────────────────────────────────────────────────────
def ensure_folder():
    """Creates data_logs/ if it doesn't exist. Safe to call every time."""
    os.makedirs(DATA_FOLDER, exist_ok=True)


# ── STEP 1: Fetch all data and attach a timestamp ─────────────────────────────
def fetch_all():
    """
    Calls all three fetchers, stamps the result with the current time,
    and returns one dictionary containing everything.

    WHAT IS A DICTIONARY?
      A dict is a labelled container:  {"label": value, "label2": value2}
      Like a form where each field has a name and a value.
    """
    now = datetime.now()

    # Two formats of the same moment:
    #   timestamp_str  → human-readable, goes INSIDE the saved files
    #   timestamp_file → filename-safe (no colons — Windows doesn't allow them)
    timestamp_str  = now.strftime("%Y-%m-%d %H:%M:%S")   # "2026-06-24 14:30:00"
    timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")   # "2026-06-24_14-30-00"

    print(f"\n⏱  Timestamp : {timestamp_str}")
    print("─" * 45)

    print("📦 Fetching crude oil price...")
    oil = get_crude_oil_price()
    print(f"   ${oil} USD/barrel" if oil is not None else "   [failed]")

    print("💵 Fetching USD → INR rate...")
    rate = get_usd_inr_rate()
    print(f"   1 USD = ₹{rate}" if rate is not None else "   [failed]")

    print(f"🌤  Fetching weather for {CITY}...")
    weather = get_weather()
    if weather:
        print(f"   {weather['temp_c']}°C  |  {weather['description'].capitalize()}"
              f"  |  Humidity {weather['humidity_pct']}%")
    else:
        print("   [failed]")

    result = {
        "timestamp":          timestamp_str,
        "oil_usd_per_barrel": oil,
        "usd_inr_rate":       rate,
        "weather":            weather,
    }

    return result, timestamp_file


# ── STEP 2a: Save full detail as JSON ────────────────────────────────────────
def save_json_snapshot(result, timestamp_file):
    """
    Writes the result dict as a nicely formatted .json file.

    WHAT IS JSON?
      Just text organised as {"key": value} pairs — any text editor can
      open it, and Python can read it back perfectly with json.load().
    """
    filename = f"snapshot_{timestamp_file}.json"
    filepath = os.path.join(DATA_FOLDER, filename)

    with open(filepath, "w") as f:
        json.dump(result, f, indent=2)   # indent=2 = human-readable formatting

    return filepath


# ── STEP 2b: Append one row to the running CSV ───────────────────────────────
def save_csv_row(result):
    """
    Adds one row to running_log.csv.
    Creates the file with headers on the very first run.
    Every run after that just appends — so you build up a history.

    WHY CSV?
      It's a plain text file (commas separate columns) that Excel,
      Google Sheets, and pandas all open directly. Great for trends.
    """
    weather = result.get("weather") or {}

    # "Flatten" the nested weather dict into one level for the CSV row
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

    # "a" = append mode → adds to the end without erasing previous rows
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()   # column names only on first run
        writer.writerow(row)


# ── ORCHESTRATOR: the one function Stage 3 (GUI) will call ───────────────────
def fetch_and_save():
    """
    Ties everything together: folder → fetch → save JSON → save CSV → report.
    Returns the result dict so the GUI can display the values on screen too.
    """
    ensure_folder()
    result, timestamp_file = fetch_all()

    print("\n💾 Saving...")
    json_path = save_json_snapshot(result, timestamp_file)
    save_csv_row(result)

    print(f"   JSON snapshot → {json_path}")
    print(f"   CSV log row   → {CSV_FILE}")
    print("\n✅ Done. Open data_logs/ in your project folder to see the files.")
    return result


# ── TEST RUN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 45)
    print("  STAGE 2 — fetch, timestamp & save")
    print("=" * 45)
    fetch_and_save()