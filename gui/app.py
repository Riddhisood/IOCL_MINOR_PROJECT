import tkinter as tk
import threading

from core.saver    import fetch_and_save
from core.errors   import FETCH_ERRORS
from gui.widgets   import DataCard

# ── Window-level visual tokens ────────────────────────────────────────────────
BG          = "#0f172a"
DIVIDER     = "#334155"
MUTED       = "#64748b"
TEXT        = "#f1f5f9"

C_OIL       = "#f59e0b"
C_FX        = "#10b981"
C_WEATHER   = "#38bdf8"
C_BTN       = "#f59e0b"
C_BTN_HOVER = "#d97706"
C_BTN_OFF   = "#334155"

F_TITLE     = ("Segoe UI", 16, "bold")
F_SUBTITLE  = ("Segoe UI",  9)
F_BTN       = ("Segoe UI", 11, "bold")
F_STATUS_LBL= ("Segoe UI",  7)
F_STATUS    = ("Segoe UI",  9)

COOLDOWN_MS = 3000   # ms before the fetch button re-enables after a click


class MonitorApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Market & Weather Monitor")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._build_header()
        self._build_cards()
        self._build_divider()
        self._build_bottom_bar()
        self._center_on_screen()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24, 16))
        tk.Label(hdr, text="🛢  MARKET & WEATHER MONITOR",
                 bg=BG, fg=TEXT, font=F_TITLE).pack(anchor="w")
        tk.Label(hdr, text="IOCL Minor Project  ·  Delhi, India",
                 bg=BG, fg=MUTED, font=F_SUBTITLE).pack(anchor="w", pady=(2, 0))

    def _build_cards(self):
        row = tk.Frame(self, bg=BG)
        row.pack(padx=30, pady=(0, 20))
        self.oil_card     = DataCard(row, "🛢   CRUDE OIL  (WTI)", "USD / barrel", C_OIL,     col=0)
        self.fx_card      = DataCard(row, "💵   USD / INR",         "₹ per dollar", C_FX,      col=1)
        self.weather_card = DataCard(row, "🌤   WEATHER  (Delhi)",  "°C",           C_WEATHER, col=2)

    def _build_divider(self):
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", padx=30)

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=30, pady=20)

        self.btn = tk.Button(
            bar, text="  🔄  FETCH & SAVE  ",
            bg=C_BTN, fg="#0f172a", font=F_BTN,
            relief="flat", cursor="hand2", padx=18, pady=10,
            command=self._on_click,
        )
        self.btn.pack(side="left")
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=C_BTN_HOVER) if str(self.btn["state"]) == "normal" else None)
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=C_BTN)       if str(self.btn["state"]) == "normal" else None)

        col = tk.Frame(bar, bg=BG)
        col.pack(side="left", padx=20)
        tk.Label(col, text="STATUS", bg=BG, fg=MUTED, font=F_STATUS_LBL).pack(anchor="w")
        self.status_var = tk.StringVar(value="Ready — click to fetch")
        tk.Label(col, textvariable=self.status_var, bg=BG, fg=TEXT, font=F_STATUS).pack(anchor="w")

    # ── Fetch flow ────────────────────────────────────────────────────────────

    def _on_click(self):
        self.btn.config(text="  ⏳  FETCHING...  ", state="disabled", bg=C_BTN_OFF)
        self.status_var.set("Contacting APIs…")
        self.oil_card.loading()
        self.fx_card.loading()
        self.weather_card.loading()
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        result = fetch_and_save()
        self.after(0, lambda: self._on_result(result))

    def _on_result(self, result):
        oil     = result.get("oil_usd_per_barrel")
        rate    = result.get("usd_inr_rate")
        weather = result.get("weather") or {}
        ts      = result.get("timestamp", "")
        failures = 0

        # Oil card
        if oil is not None:
            self.oil_card.normal(f"${oil}")
        else:
            failures += 1
            reason = FETCH_ERRORS.get("oil", "")
            self.oil_card.error(reason, soft="closed" in (reason or "").lower())

        # Forex card
        if rate is not None:
            self.fx_card.normal(f"{rate}")
        else:
            failures += 1
            reason = FETCH_ERRORS.get("fx", "")
            self.fx_card.error(reason, soft="closed" in (reason or "").lower())

        # Weather card
        if weather:
            sub = (f"{weather.get('description','').capitalize()}  ·  "
                   f"Humidity {weather.get('humidity_pct','—')}%  ·  "
                   f"Wind {weather.get('wind_kph','—')} kph")
            self.weather_card.normal(str(weather.get("temp_c", "—")), sub)
        else:
            failures += 1
            self.weather_card.error(FETCH_ERRORS.get("weather", ""))

        # Status bar
        if failures == 0:
            self.status_var.set(f"✅  Saved at {ts}")
        elif failures == 3:
            self.status_var.set("❌  All sources failed — check internet")
        else:
            self.status_var.set(f"⚠   {failures} source(s) failed — see cards above  |  {ts}")

        self.after(COOLDOWN_MS, self._re_enable_btn)

    def _re_enable_btn(self):
        self.btn.config(text="  🔄  FETCH & SAVE  ", state="normal", bg=C_BTN)

    # ── Utility ───────────────────────────────────────────────────────────────

    def _center_on_screen(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")