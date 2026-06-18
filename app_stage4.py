"""
STAGE 4: Error Handling + Settings Panel
-----------------------------------------
New concepts in this stage:

  try / except      - gracefully catch failures so the app does not crash
                      if one API is down or slow. Each fetcher returns either
                      a value OR a string starting with "ERR:".

  ttk.Notebook      - a tabbed widget for the Settings tab.

  json config file  - saves city/currency/API key to data/config.json so
                      settings survive closing and reopening the app.

HOW TO RUN:
    python app_stage4.py
"""

import csv
import json
import threading
import requests
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

# ---- DEFAULT CONFIG ----
DEFAULT_CONFIG = {
    "alpha_vantage_key": "B2ATNTCJ5MQCGT68",
    "city":              "Delhi",
    "currency":          "INR",
}

DATA_DIR    = Path("data")
CONFIG_PATH = DATA_DIR / "config.json"

# ---- COLOURS ----
BG      = "#0f172a"
CARD_BG = "#1e293b"
ACCENT  = "#38bdf8"
TEXT    = "#f1f5f9"
SUBTEXT = "#94a3b8"
WARNING = "#fb923c"
ERROR_C = "#f87171"


# =================== CONFIG HELPERS ===================

def load_config():
    if CONFIG_PATH.exists():
        saved = json.loads(CONFIG_PATH.read_text())
        return {**DEFAULT_CONFIG, **saved}
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    DATA_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# =================== FETCHERS ===================

def get_crude_oil_price(api_key: str):
    """Returns a float on success, or 'ERR: ...' string on failure."""
    try:
        data = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "WTI", "interval": "daily", "apikey": api_key},
            timeout=10,
        ).json()
        return float(data["data"][0]["value"])
    except (KeyError, IndexError, ValueError):
        info = data.get("Information") or data.get("Note") or "Unexpected response"
        return f"ERR: {info[:80]}"
    except requests.exceptions.Timeout:
        return "ERR: Request timed out"
    except Exception as e:
        return f"ERR: {e}"


def get_usd_exchange_rate(currency: str):
    try:
        data = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD", "to": currency},
            timeout=10,
        ).json()
        return data["rates"][currency]
    except requests.exceptions.Timeout:
        return "ERR: Request timed out"
    except (KeyError, TypeError):
        return f"ERR: Currency '{currency}' not found"
    except Exception as e:
        return f"ERR: {e}"


def get_weather(city: str):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        ).json()
        if not geo.get("results"):
            return f"ERR: City '{city}' not found"
        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=10,
        ).json()
        cw = w["current_weather"]
        return {"city": city, "temperature_c": cw["temperature"], "windspeed_kph": cw["windspeed"]}
    except requests.exceptions.Timeout:
        return "ERR: Request timed out"
    except Exception as e:
        return f"ERR: {e}"


# =================== SAVING ===================

def save_snapshot(record: dict):
    DATA_DIR.mkdir(exist_ok=True)
    safe_ts = record["timestamp"].replace(":", "-").replace(" ", "_")
    path = DATA_DIR / f"snapshot_{safe_ts}.json"
    path.write_text(json.dumps(record, indent=2, default=str))

def append_to_log(record: dict, currency: str):
    DATA_DIR.mkdir(exist_ok=True)
    log_path = DATA_DIR / "log.csv"
    col = f"usd_to_{currency.lower()}"
    headers = ["timestamp", "oil_usd_per_barrel", col, "city", "temperature_c", "windspeed_kph"]
    write_header = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if write_header:
            writer.writeheader()
        wx = record.get("weather") if isinstance(record.get("weather"), dict) else {}
        writer.writerow({
            "timestamp":          record["timestamp"],
            "oil_usd_per_barrel": record.get("oil", ""),
            col:                  record.get("rate", ""),
            "city":               wx.get("city", record.get("city", "")),
            "temperature_c":      wx.get("temperature_c", ""),
            "windspeed_kph":      wx.get("windspeed_kph", ""),
        })


# =================== GUI ===================

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title("Market & Weather Tracker")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._build_ui()
        self._center_window(540, 520)

    # ---------- layout ----------

    def _build_ui(self):
        # header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(18, 4))
        tk.Label(hdr, text="Market & Weather Tracker",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        self.subtitle_var = tk.StringVar(value=self._subtitle())
        tk.Label(hdr, textvariable=self.subtitle_var,
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 10)).pack(anchor="w")

        # notebook tabs
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook",      background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",  background=CARD_BG, foreground=SUBTEXT,
                        padding=[12, 6],  font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=8)

        dash = tk.Frame(nb, bg=BG)
        nb.add(dash, text="  Dashboard  ")
        self._build_dashboard(dash)

        sett = tk.Frame(nb, bg=BG)
        nb.add(sett, text="  Settings  ")
        self._build_settings(sett)

        # status bar
        self.status_var = tk.StringVar(value="Ready -- click Fetch Now to begin")
        tk.Label(self, textvariable=self.status_var,
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(pady=(0, 12))

    def _build_dashboard(self, parent):
        # data cards
        cards_row = tk.Frame(parent, bg=BG)
        cards_row.pack(fill="x", pady=(10, 8))
        self.card_oil = self._make_card(cards_row, "Crude Oil",     "WTI",                          "-- USD/bbl")
        self.card_fx  = self._make_card(cards_row, "Exchange Rate", f"USD \u2192 {self.cfg['currency']}", "--")
        self.card_wx  = self._make_card(cards_row, "Weather",       self.cfg["city"],               "--\u00b0C")
        for card in (self.card_oil, self.card_fx, self.card_wx):
            card.pack(side="left", expand=True, fill="both", padx=4)

        # fetch button
        self.btn = tk.Button(
            parent, text="Fetch Now", command=self._on_fetch,
            bg=ACCENT, fg="#0f172a", activebackground="#7dd3fc",
            font=("Segoe UI", 12, "bold"), bd=0, relief="flat",
            padx=20, pady=10, cursor="hand2",
        )
        self.btn.pack(pady=(4, 8))

        # history log
        hist = tk.Frame(parent, bg=CARD_BG)
        hist.pack(fill="both", expand=True, pady=(0, 4))
        tk.Label(hist, text="Fetch history", bg=CARD_BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(6, 0))
        self.log_box = tk.Text(
            hist, bg=CARD_BG, fg=TEXT, font=("Consolas", 9),
            bd=0, highlightthickness=0, state="disabled", height=6,
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(2, 8))

    def _build_settings(self, parent):
        def labeled_entry(label_text, var, show=""):
            tk.Label(parent, text=label_text, bg=BG, fg=SUBTEXT,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(10, 0))
            e = tk.Entry(parent, textvariable=var, bg=CARD_BG, fg=TEXT,
                         insertbackground=TEXT, bd=0, font=("Segoe UI", 10),
                         show=show, width=46)
            e.pack(padx=20, pady=(2, 0), anchor="w", ipady=6)

        self.s_av_key = tk.StringVar(value=self.cfg["alpha_vantage_key"])
        self.s_city   = tk.StringVar(value=self.cfg["city"])
        self.s_curr   = tk.StringVar(value=self.cfg["currency"])

        labeled_entry("Alpha Vantage API Key", self.s_av_key, show="*")
        labeled_entry("City", self.s_city)
        labeled_entry("Currency code  (e.g. INR, EUR, JPY, GBP)", self.s_curr)

        tk.Button(
            parent, text="Save Settings", command=self._save_settings,
            bg=ACCENT, fg="#0f172a", font=("Segoe UI", 10, "bold"),
            bd=0, relief="flat", padx=16, pady=8, cursor="hand2",
        ).pack(padx=20, pady=16, anchor="w")

        self.settings_msg = tk.StringVar(value="")
        tk.Label(parent, textvariable=self.settings_msg,
                 bg=BG, fg=ACCENT, font=("Segoe UI", 9)).pack(padx=20, anchor="w")

        tk.Label(parent, bg=BG, fg=SUBTEXT, font=("Segoe UI", 8),
                 text="Your key is stored locally in data/config.json.\nNever share or upload that file."
                 ).pack(padx=20, pady=(16, 0), anchor="w")

    def _make_card(self, parent, title, subtitle, initial):
        frame = tk.Frame(parent, bg=CARD_BG, pady=12, padx=12)
        tk.Label(frame, text=title,    bg=CARD_BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(frame, text=subtitle, bg=CARD_BG, fg=SUBTEXT, font=("Segoe UI", 8)).pack(anchor="w")
        var = tk.StringVar(value=initial)
        tk.Label(frame, textvariable=var, bg=CARD_BG, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(4, 0))
        frame.value_var = var
        return frame

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _subtitle(self):
        return f"Crude Oil  |  USD\u2192{self.cfg['currency']}  |  {self.cfg['city']} Weather"

    # ---------- settings ----------

    def _save_settings(self):
        self.cfg["alpha_vantage_key"] = self.s_av_key.get().strip()
        self.cfg["city"]              = self.s_city.get().strip()
        self.cfg["currency"]          = self.s_curr.get().strip().upper()
        save_config(self.cfg)
        self.subtitle_var.set(self._subtitle())
        self.settings_msg.set("Saved! Changes take effect on next fetch.")

    # ---------- fetch ----------

    def _on_fetch(self):
        self.btn.config(state="disabled", text="Fetching...", bg=SUBTEXT)
        self.status_var.set("Contacting APIs...")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            oil     = get_crude_oil_price(self.cfg["alpha_vantage_key"])
            rate    = get_usd_exchange_rate(self.cfg["currency"])
            weather = get_weather(self.cfg["city"])
            record  = {
                "timestamp": ts,
                "oil":       oil,
                "rate":      rate,
                "weather":   weather,
                "city":      self.cfg["city"],
                "currency":  self.cfg["currency"],
            }
            save_snapshot(record)
            append_to_log(record, self.cfg["currency"])
            self.after(0, lambda: self._update_ui(record))
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))

    def _fmt(self, val, suffix=""):
        """Return (display_string, colour). Red if the value is an error."""
        if isinstance(val, str) and val.startswith("ERR:"):
            return "Error", ERROR_C
        return f"{val}{suffix}", TEXT

    def _update_ui(self, r):
        oil_str,  oil_col  = self._fmt(r["oil"],  " USD")
        rate_str, rate_col = self._fmt(r["rate"])

        wx = r["weather"]
        if isinstance(wx, dict):
            wx_str, wx_col = f"{wx['temperature_c']}\u00b0C", TEXT
        else:
            wx_str, wx_col = "Error", ERROR_C

        self.card_oil.value_var.set(oil_str)
        self.card_fx.value_var.set(rate_str)
        self.card_wx.value_var.set(wx_str)

        # tint value labels red on error
        for card, col in ((self.card_oil, oil_col), (self.card_fx, rate_col), (self.card_wx, wx_col)):
            for widget in card.pack_slaves():
                if isinstance(widget, tk.Label) and "bold" in str(widget.cget("font")):
                    widget.config(fg=col)

        wind = wx.get("windspeed_kph", "?") if isinstance(wx, dict) else "?"
        log_line = (
            f"[{r['timestamp']}]  "
            f"Oil: {r['oil']}  |  "
            f"USD\u2192{r['currency']}: {r['rate']}  |  "
            f"{wx_str}  wind {wind} kph\n"
        )
        self.log_box.config(state="normal")
        self.log_box.insert("end", log_line)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

        self.status_var.set(f"Last fetched: {r['timestamp']}  |  Saved to data/")
        self.btn.config(state="normal", text="Fetch Now", bg=ACCENT)

    def _show_error(self, msg):
        self.status_var.set(f"Unexpected error: {msg}")
        self.btn.config(state="normal", text="Fetch Now", bg=WARNING)


if __name__ == "__main__":
    app = App()
    app.mainloop()