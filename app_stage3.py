"""
STAGE 3: Desktop Window (tkinter)
-----------------------------------
tkinter is Python's built-in GUI library -- no pip install needed.
It lets you create windows, buttons, labels, and frames with pure Python.

New concepts introduced here:

  tk.Tk()           - creates the main application window
  tk.Label()        - a piece of text on screen
  tk.Button()       - a clickable button
  tk.Frame()        - an invisible box used to group and position other widgets
  .grid()           - places a widget at a row/column inside its parent
  .config()         - changes a widget's properties after it has been created
  threading.Thread  - runs the fetch in the background so the window does not freeze
                      while waiting for the internet. Without this, clicking Fetch
                      would lock up the whole window until all three APIs respond.
  .after(0, fn)     - safely schedules a UI update from a background thread
                      (tkinter is not thread-safe, so we never touch widgets
                       directly from threads -- we schedule updates instead)

HOW TO RUN:
    python app_stage3.py

A window will open. Click "Fetch Now" to pull data and save it.
"""

import csv
import json
import threading
import requests
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

# ---- CONFIG ----
ALPHA_VANTAGE_API_KEY = "B2ATNTCJ5MQCGT68"
CITY = "Delhi"
TARGET_CURRENCY = "INR"
DATA_DIR = Path("data")

# ---- COLOURS ----
BG        = "#0f172a"   # dark navy background
CARD_BG   = "#1e293b"   # slightly lighter card background
ACCENT    = "#38bdf8"   # sky blue  -- used for the button and headings
TEXT      = "#f1f5f9"   # near-white text
SUBTEXT   = "#94a3b8"   # muted grey for labels
SUCCESS   = "#4ade80"   # green  -- used when fetch succeeds
WARNING   = "#fb923c"   # orange -- used on errors


# =================== FETCHERS (same as Stage 2) ===================

def get_crude_oil_price():
    url = "https://www.alphavantage.co/query"
    params = {"function": "WTI", "interval": "daily", "apikey": ALPHA_VANTAGE_API_KEY}
    data = requests.get(url, params=params, timeout=10).json()
    try:
        return float(data["data"][0]["value"])
    except (KeyError, IndexError, ValueError, TypeError):
        return None

def get_usd_exchange_rate(target_currency=TARGET_CURRENCY):
    data = requests.get("https://api.frankfurter.app/latest",
                        params={"from": "USD", "to": target_currency}, timeout=10).json()
    try:
        return data["rates"][target_currency]
    except (KeyError, TypeError):
        return None

def get_weather(city=CITY):
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1}, timeout=10).json()
    if not geo.get("results"):
        return None
    lat = geo["results"][0]["latitude"]
    lon = geo["results"][0]["longitude"]
    w = requests.get("https://api.open-meteo.com/v1/forecast",
                     params={"latitude": lat, "longitude": lon, "current_weather": True},
                     timeout=10).json()
    try:
        cw = w["current_weather"]
        return {"city": city, "temperature_c": cw["temperature"], "windspeed_kph": cw["windspeed"]}
    except (KeyError, TypeError):
        return None


# =================== SAVING (same as Stage 2) ===================

def save_snapshot(record):
    DATA_DIR.mkdir(exist_ok=True)
    safe_ts = record["timestamp"].replace(":", "-").replace(" ", "_")
    path = DATA_DIR / f"snapshot_{safe_ts}.json"
    path.write_text(json.dumps(record, indent=2))

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
            "timestamp":         record["timestamp"],
            "oil_usd_per_barrel": record["oil_usd_per_barrel"],
            col:                 record["usd_to_inr"],
            "city":              wx.get("city", ""),
            "temperature_c":     wx.get("temperature_c", ""),
            "windspeed_kph":     wx.get("windspeed_kph", ""),
        })


# =================== GUI ===================

class App(tk.Tk):
    """
    We define the whole application as a class that inherits from tk.Tk.
    Inheriting means our App IS a window -- it has all of tk.Tk's abilities
    plus the extra things we add inside __init__ and our own methods.
    """

    def __init__(self):
        super().__init__()                        # set up the window itself
        self.title("Market & Weather Tracker")
        self.configure(bg=BG)
        self.resizable(False, False)              # fixed size -- no stretching

        self._build_ui()
        self._center_window(520, 480)

    # ---------- layout ----------

    def _build_ui(self):
        pad = {"padx": 20, "pady": 8}

        # ---- header ----
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(20, 4))

        tk.Label(header, text="Market & Weather Tracker",
                 bg=BG, fg=ACCENT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text=f"Crude Oil  |  USD\u2192{TARGET_CURRENCY}  |  {CITY} Weather",
                 bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 10)).pack(anchor="w")

        # ---- cards row ----
        cards_row = tk.Frame(self, bg=BG)
        cards_row.pack(fill="x", padx=20, pady=12)

        self.card_oil     = self._make_card(cards_row, "Crude Oil", "WTI", "-- USD/bbl")
        self.card_fx      = self._make_card(cards_row, "Exchange Rate", f"USD \u2192 {TARGET_CURRENCY}", "--")
        self.card_weather = self._make_card(cards_row, "Weather", CITY, "--\u00b0C")

        self.card_oil.pack    (side="left", expand=True, fill="both", padx=(0, 6))
        self.card_fx.pack     (side="left", expand=True, fill="both", padx=6)
        self.card_weather.pack(side="left", expand=True, fill="both", padx=(6, 0))

        # ---- fetch button ----
        self.btn = tk.Button(
            self,
            text="Fetch Now",
            command=self._on_fetch,
            bg=ACCENT, fg="#0f172a",
            activebackground="#7dd3fc",
            font=("Segoe UI", 12, "bold"),
            bd=0, relief="flat",
            padx=20, pady=10,
            cursor="hand2",
        )
        self.btn.pack(pady=(4, 8))

        # ---- log history box ----
        log_frame = tk.Frame(self, bg=CARD_BG, bd=0)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        tk.Label(log_frame, text="Fetch history",
                 bg=CARD_BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(6, 0))

        self.log_box = tk.Text(
            log_frame,
            bg=CARD_BG, fg=TEXT,
            font=("Consolas", 9),
            bd=0, highlightthickness=0,
            state="disabled",     # read-only; we enable briefly to insert text
            height=5,
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(2, 8))

        # ---- status bar ----
        self.status_var = tk.StringVar(value="Ready -- click Fetch Now to begin")
        tk.Label(self, textvariable=self.status_var,
                 bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(pady=(0, 14))

    def _make_card(self, parent, title, subtitle, initial_value):
        """Build one data card and return a controller object so we can update its value later."""
        frame = tk.Frame(parent, bg=CARD_BG, pady=12, padx=12)
        tk.Label(frame, text=title,    bg=CARD_BG, fg=SUBTEXT,  font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(frame, text=subtitle, bg=CARD_BG, fg=SUBTEXT,  font=("Segoe UI", 8)).pack(anchor="w")
        value_var = tk.StringVar(value=initial_value)
        tk.Label(frame, textvariable=value_var,
                 bg=CARD_BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(4, 0))
        frame.value_var = value_var    # stash the var on the frame so callers can reach it
        return frame

    def _center_window(self, w, h):
        """Position the window in the middle of the screen on startup."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ---------- fetch logic ----------

    def _on_fetch(self):
        """Called when the button is clicked. Disables the button, then starts a background thread."""
        self.btn.config(state="disabled", text="Fetching...", bg=SUBTEXT)
        self.status_var.set("Contacting APIs...")
        # Run the slow network calls in a separate thread so the window stays responsive
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        """
        Runs in a background thread. Calls all three APIs and saves results.
        Never touches tkinter widgets directly -- schedules updates with .after(0, ...).
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            oil     = get_crude_oil_price()
            rate    = get_usd_exchange_rate()
            weather = get_weather()

            record = {
                "timestamp":          timestamp,
                "oil_usd_per_barrel": oil,
                "usd_to_inr":         rate,
                "weather":            weather,
            }
            save_snapshot(record)
            append_to_log(record)

            # Schedule the UI update back on the main thread
            self.after(0, lambda: self._update_ui(record))

        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))

    def _update_ui(self, record):
        """Called on the main thread after a successful fetch. Updates all cards and the log."""
        oil     = record["oil_usd_per_barrel"]
        rate    = record["usd_to_inr"]
        weather = record["weather"] or {}
        ts      = record["timestamp"]

        self.card_oil.value_var.set(f"{oil} USD" if oil else "Error")
        self.card_fx.value_var.set(f"{rate}" if rate else "Error")
        self.card_weather.value_var.set(
            f"{weather.get('temperature_c', '--')}\u00b0C" if weather else "Error"
        )

        wind = weather.get("windspeed_kph", "?")
        log_line = f"[{ts}]  Oil: {oil}  |  USD\u2192{TARGET_CURRENCY}: {rate}  |  {weather.get('temperature_c','?')}\u00b0C  wind {wind} kph\n"
        self.log_box.config(state="normal")
        self.log_box.insert("end", log_line)
        self.log_box.see("end")          # scroll to the latest entry
        self.log_box.config(state="disabled")

        self.status_var.set(f"Last fetched: {ts}  |  Saved to data/")
        self.btn.config(state="normal", text="Fetch Now", bg=ACCENT)


    def _show_error(self, msg):
        """Called on the main thread if the fetch thread crashes."""
        self.status_var.set(f"Error: {msg}")
        self.btn.config(state="normal", text="Fetch Now", bg=WARNING)


# =================== ENTRY POINT ===================

if __name__ == "__main__":
    app = App()
    app.mainloop()    # hands control to tkinter; it listens for clicks/keypresses until the window closes