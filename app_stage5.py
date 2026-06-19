"""
STAGE 5: View History Tab (date filtering + summary table)
--------------------------------------------------------------
Everything from Stage 4 (error handling, Settings tab) is unchanged.
This stage adds a third tab: History.

New concepts in this stage:

  ttk.Treeview      - a table widget. Each row is one record from log.csv,
                      each column is one field (timestamp, oil price, etc).
                      This is the standard way to show tabular data in tkinter.

  ttk.Combobox      - a dropdown selector. Used here to pick a quick date
                      range: Today / Last 7 Days / Last 30 Days / All Time /
                      Custom Range.

  csv.DictReader    - reads log.csv back OUT as a list of dicts (the mirror
                      image of csv.DictWriter, which we used to write it).

  Pure logic functions (compute_range, filter_records, compute_summary) are
  kept as plain functions with no tkinter code inside them. This matters:
  it means we could test the filtering math by itself (and we did, before
  ever touching the window) without needing a screen at all. Separating
  "logic" from "UI" like this is a habit worth keeping as your projects grow.

HOW TO RUN:
    python app_stage5.py
"""

import csv
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
import requests
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


# =================== HISTORY LOGIC (pure functions, no tkinter) ===================
# These were unit-tested separately before being wired into the UI below.

TS_FORMAT = "%Y-%m-%d %H:%M:%S"

def parse_timestamp(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, TS_FORMAT)


def compute_range(choice: str, custom_from: str = "", custom_to: str = ""):
    """Turn a dropdown choice into a (start, end) datetime pair. (None, None) means 'no filter'."""
    now = datetime.now()
    if choice == "Today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if choice == "Last 7 Days":
        return now - timedelta(days=7), now
    if choice == "Last 30 Days":
        return now - timedelta(days=30), now
    if choice == "Custom Range":
        start = datetime.strptime(custom_from.strip(), "%Y-%m-%d")
        end = datetime.strptime(custom_to.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        return start, end
    return None, None  # "All Time"


def read_log_records(log_path: Path):
    """Read log.csv into a list of dicts. Returns [] if the file does not exist yet."""
    if not log_path.exists():
        return []
    with open(log_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def filter_records(records, start, end):
    """Keep only rows whose timestamp falls within [start, end]. None/None = keep everything."""
    if start is None and end is None:
        return records
    result = []
    for row in records:
        try:
            ts = parse_timestamp(row["timestamp"])
        except (KeyError, ValueError):
            continue  # skip rows with a broken/missing timestamp rather than crashing
        if start <= ts <= end:
            result.append(row)
    return result


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_summary(records, fx_column: str):
    """Return (count, avg_oil_or_None, avg_fx_or_None), skipping any 'ERR:' rows safely."""
    oil_vals = [v for v in (safe_float(r.get("oil_usd_per_barrel")) for r in records) if v is not None]
    fx_vals  = [v for v in (safe_float(r.get(fx_column)) for r in records) if v is not None]
    avg_oil = round(sum(oil_vals) / len(oil_vals), 2) if oil_vals else None
    avg_fx  = round(sum(fx_vals) / len(fx_vals), 2) if fx_vals else None
    return len(records), avg_oil, avg_fx


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
        self._center_window(560, 600)

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

        hist_tab = tk.Frame(nb, bg=BG)
        nb.add(hist_tab, text="  History  ")
        self._build_history_tab(hist_tab)

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

    def _build_history_tab(self, parent):
        # ---- style the Treeview (table) and Combobox (dropdown) to match the dark theme ----
        style = ttk.Style(self)
        style.configure("Treeview",
                         background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT,
                         borderwidth=0, rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                         background=BG, foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#0f172a")])

        # ---- filter controls row ----
        controls = tk.Frame(parent, bg=BG)
        controls.pack(fill="x", padx=4, pady=(12, 6))

        tk.Label(controls, text="Show:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).grid(row=0, column=0, padx=(0, 6))

        self.range_choice = tk.StringVar(value="Last 7 Days")
        range_box = ttk.Combobox(
            controls, textvariable=self.range_choice, state="readonly", width=14,
            values=["Today", "Last 7 Days", "Last 30 Days", "All Time", "Custom Range"],
        )
        range_box.grid(row=0, column=1, padx=(0, 10))
        range_box.bind("<<ComboboxSelected>>", lambda e: self._on_range_choice_changed())

        # custom date entries -- hidden unless "Custom Range" is selected
        self.custom_from = tk.StringVar()
        self.custom_to   = tk.StringVar()
        self.from_entry = tk.Entry(controls, textvariable=self.custom_from, width=11,
                                    bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0)
        self.to_entry   = tk.Entry(controls, textvariable=self.custom_to, width=11,
                                    bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0)
        self.from_label = tk.Label(controls, text="From (YYYY-MM-DD)", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        self.to_label   = tk.Label(controls, text="To (YYYY-MM-DD)",   bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        # not gridded yet -- _on_range_choice_changed() will show/hide them

        tk.Button(controls, text="Apply", command=self._apply_history_filter,
                  bg=ACCENT, fg="#0f172a", font=("Segoe UI", 9, "bold"),
                  bd=0, relief="flat", padx=12, pady=4, cursor="hand2",
                  ).grid(row=0, column=6, padx=(8, 0))

        # ---- summary line ----
        self.history_summary_var = tk.StringVar(value="Click Apply to load history.")
        tk.Label(parent, textvariable=self.history_summary_var,
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=4, pady=(0, 6))

        # ---- table ----
        table_frame = tk.Frame(parent, bg=BG)
        table_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        columns = ("time", "oil", "fx", "city", "temp", "wind")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        headings = {
            "time": "Time", "oil": "Oil (USD/bbl)", "fx": f"USD\u2192{self.cfg['currency']}",
            "city": "City", "temp": "Temp (\u00b0C)", "wind": "Wind (kph)",
        }
        widths = {"time": 140, "oil": 90, "fx": 80, "city": 80, "temp": 70, "wind": 70}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._on_range_choice_changed()  # set initial visibility of custom-date fields
        self._apply_history_filter()     # load data on first open

    def _on_range_choice_changed(self):
        """Show the custom date entry boxes only when 'Custom Range' is selected."""
        if self.range_choice.get() == "Custom Range":
            self.from_label.grid(row=1, column=1, sticky="w")
            self.from_entry.grid(row=0, column=2, padx=(0, 6))
            self.to_label.grid(row=1, column=3, sticky="w")
            self.to_entry.grid(row=0, column=3, padx=(0, 6))
        else:
            self.from_label.grid_forget()
            self.from_entry.grid_forget()
            self.to_label.grid_forget()
            self.to_entry.grid_forget()

    def _apply_history_filter(self):
        """Read log.csv, filter by the selected date range, and refresh the table + summary."""
        log_path = DATA_DIR / "log.csv"
        records = read_log_records(log_path)

        if not records:
            self.history_summary_var.set("No data yet -- go to Dashboard and click Fetch Now first.")
            self.tree.delete(*self.tree.get_children())
            return

        try:
            start, end = compute_range(self.range_choice.get(), self.custom_from.get(), self.custom_to.get())
        except ValueError:
            self.history_summary_var.set("Custom dates must be in YYYY-MM-DD format, e.g. 2026-06-01")
            return

        filtered = filter_records(records, start, end)
        filtered = list(reversed(filtered))  # newest first

        # refresh table
        self.tree.delete(*self.tree.get_children())
        for row in filtered:
            self.tree.insert("", "end", values=(
                row.get("timestamp", ""),
                row.get("oil_usd_per_barrel", ""),
                row.get(f"usd_to_{self.cfg['currency'].lower()}", ""),
                row.get("city", ""),
                row.get("temperature_c", ""),
                row.get("windspeed_kph", ""),
            ))

        # refresh summary
        fx_col = f"usd_to_{self.cfg['currency'].lower()}"
        count, avg_oil, avg_fx = compute_summary(filtered, fx_col)
        oil_str = f"${avg_oil}" if avg_oil is not None else "n/a"
        fx_str  = f"{avg_fx}" if avg_fx is not None else "n/a"
        self.history_summary_var.set(
            f"{count} record(s)  |  Avg oil: {oil_str}  |  Avg USD\u2192{self.cfg['currency']}: {fx_str}"
        )

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