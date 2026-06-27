import os
from dotenv import load_dotenv

# Read the .env file that lives next to main.py.
# load_dotenv() is safe to call even if .env doesn't exist — it just does nothing.
load_dotenv()

# ── Data sources ──────────────────────────────────────────────────────────────
CITY                = "Delhi"           # change this to any city OpenWeatherMap knows
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# ── Storage ───────────────────────────────────────────────────────────────────
DATA_FOLDER = "data_logs"              # folder created next to main.py
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