"""
STAGE 3 (v2): Desktop GUI — with graceful error handling
---------------------------------------------------------
New in this version:

  1. LAST KNOWN VALUES — values from the previous successful fetch stay
     visible while a new fetch is running, with a "(cached)" badge.

  2. PER-CARD ERROR STATES — if one API fails, that card goes red and
     shows the exact reason. The other two cards stay normal.

  3. GLOBAL STATUS BAR — shows a summary message beneath the button:
     "✅ Saved at 14:30"  or  "⚠ 1 source failed — see cards above"

  4. BUTTON COOLDOWN — button stays disabled for 3 seconds after a fetch
     to avoid hammering APIs accidentally.
"""

import tkinter as tk
import threading
from app_stage2 import fetch_and_save
from app_stage1 import FETCH_ERRORS   # the error store populated by each fetcher


# ── TOKENS ────────────────────────────────────────────────────────────────────
BG          = "#0f172a"
CARD        = "#1e293b"
TEXT        = "#f1f5f9"
MUTED       = "#64748b"
DIVIDER     = "#334155"

C_OIL       = "#f59e0b"   # amber
C_FX        = "#10b981"   # emerald
C_WEATHER   = "#38bdf8"   # sky blue
C_ERROR     = "#ef4444"   # red  — card accent when fetch failed
C_WARN      = "#f97316"   # orange — e.g. markets closed (soft failure)
C_BTN       = "#f59e0b"
C_BTN_HOVER = "#d97706"
C_BTN_OFF   = "#334155"

F_APP_TITLE = ("Segoe UI", 16, "bold")
F_SUBTITLE  = ("Segoe UI",  9)
F_CARD_HDR  = ("Segoe UI",  8, "bold")
F_NUMBER    = ("Segoe UI", 34, "bold")
F_UNIT      = ("Segoe UI",  9)
F_ERR_MSG   = ("Segoe UI",  8)
F_BADGE     = ("Segoe UI",  7, "bold")
F_BTN       = ("Segoe UI", 11, "bold")
F_STATUS_LBL= ("Segoe UI",  7)
F_STATUS    = ("Segoe UI",  9)

COOLDOWN_MS = 3000   # milliseconds to wait before re-enabling button


# ── DATA CARD WIDGET ──────────────────────────────────────────────────────────
class DataCard(tk.Frame):
    """
    A self-contained card for one data point (oil / fx / weather).

    It manages its own visual state:
      normal(value)  → coloured accent, big number
      loading()      → dims to "…" while fetching
      error(reason)  → red accent, shows the reason string
    """

    def __init__(self, parent, title, unit, accent, col, sub_label=False):
        super().__init__(parent, bg=CARD, padx=22, pady=0)
        self.grid(row=0, column=col,
                  padx=(0 if col == 0 else 12), sticky="nsew")

        self._accent  = accent   # original colour, restored after errors
        self._unit    = unit

        # ── top accent stripe ──
        self._stripe = tk.Frame(self, height=3, bg=accent)
        self._stripe.pack(fill="x")

        # ── header row: title + cached badge ──
        hdr = tk.Frame(self, bg=CARD)
        hdr.pack(fill="x", pady=(14, 0))
        tk.Label(hdr, text=title, bg=CARD, fg=MUTED,
                 font=F_CARD_HDR).pack(side="left")
        self._badge = tk.Label(hdr, text="", bg=CARD, fg=MUTED, font=F_BADGE)
        self._badge.pack(side="left", padx=(6, 0))

        # ── big number ──
        self._num_var = tk.StringVar(value="—")
        self._num_lbl = tk.Label(self, textvariable=self._num_var,
                                 bg=CARD, fg=accent, font=F_NUMBER)
        self._num_lbl.pack(anchor="w", pady=(4, 0))

        # ── unit label ──
        tk.Label(self, text=unit, bg=CARD, fg=MUTED, font=F_UNIT).pack(anchor="w")

        # ── optional sub-line (weather description / error reason) ──
        self._sub_var = tk.StringVar(value="")
        self._sub_lbl = tk.Label(self, textvariable=self._sub_var,
                                 bg=CARD, fg=TEXT, font=F_ERR_MSG,
                                 wraplength=200, justify="left")
        self._sub_lbl.pack(anchor="w", pady=(5, 0))

        tk.Frame(self, bg=CARD, height=18).pack()   # bottom padding

        self._last_good = None   # remembers the last successful value string


    def normal(self, value_str, sub=""):
        """Show a real value with the card's original accent colour."""
        self._last_good = value_str
        self._stripe.config(bg=self._accent)
        self._num_lbl.config(fg=self._accent)
        self._num_var.set(value_str)
        self._sub_var.set(sub)
        self._sub_lbl.config(fg=TEXT)
        self._badge.config(text="")


    def loading(self):
        """Dim the card while the fetch is running; keep last known value."""
        if self._last_good:
            # Show last known value in muted colour so user isn't left with blanks
            self._num_var.set(self._last_good)
            self._num_lbl.config(fg=MUTED)
            self._badge.config(text="CACHED")
        else:
            self._num_var.set("…")
            self._num_lbl.config(fg=MUTED)
        self._stripe.config(bg=MUTED)
        self._sub_var.set("")


    def error(self, reason="", soft=False):
        """
        Mark the card as failed.
        soft=True  → orange (e.g. markets closed — data exists, just unavailable now)
        soft=False → red (real error: no internet, bad key, etc.)
        """
        colour = C_WARN if soft else C_ERROR
        self._stripe.config(bg=colour)
        self._num_lbl.config(fg=colour)

        if self._last_good:
            # Keep the last value visible with a "STALE" badge
            self._num_var.set(self._last_good)
            self._badge.config(text="STALE")
        else:
            self._num_var.set("—")
            self._badge.config(text="")

        self._sub_var.set(reason or "Could not retrieve data")
        self._sub_lbl.config(fg=colour)


# ── MAIN WINDOW ───────────────────────────────────────────────────────────────
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


    def _build_header(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24, 16))
        tk.Label(hdr, text="🛢  MARKET & WEATHER MONITOR",
                 bg=BG, fg=TEXT, font=F_APP_TITLE).pack(anchor="w")
        tk.Label(hdr, text="IOCL Minor Project  ·  Delhi, India",
                 bg=BG, fg=MUTED, font=F_SUBTITLE).pack(anchor="w", pady=(2, 0))


    def _build_cards(self):
        row = tk.Frame(self, bg=BG)
        row.pack(padx=30, pady=(0, 20))

        self.oil_card     = DataCard(row, "🛢   CRUDE OIL  (WTI)",  "USD / barrel",  C_OIL,     col=0)
        self.fx_card      = DataCard(row, "💵   USD / INR",          "₹ per dollar",  C_FX,      col=1)
        self.weather_card = DataCard(row, "🌤   WEATHER  (Delhi)",   "°C",            C_WEATHER, col=2, sub_label=True)


    def _build_divider(self):
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", padx=30)


    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=30, pady=20)

        self.btn = tk.Button(
            bar,
            text="  🔄  FETCH & SAVE  ",
            bg=C_BTN, fg="#0f172a",
            font=F_BTN, relief="flat",
            cursor="hand2", padx=18, pady=10,
            command=self._on_click,
        )
        self.btn.pack(side="left")
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=C_BTN_HOVER) if str(self.btn["state"]) == "normal" else None)
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=C_BTN)       if str(self.btn["state"]) == "normal" else None)

        status_col = tk.Frame(bar, bg=BG)
        status_col.pack(side="left", padx=20)
        tk.Label(status_col, text="STATUS", bg=BG, fg=MUTED, font=F_STATUS_LBL).pack(anchor="w")
        self.status_var = tk.StringVar(value="Ready — click to fetch")
        tk.Label(status_col, textvariable=self.status_var,
                 bg=BG, fg=TEXT, font=F_STATUS).pack(anchor="w")


    # ── FETCH FLOW ────────────────────────────────────────────────────────────

    def _on_click(self):
        self.btn.config(text="  ⏳  FETCHING...  ", state="disabled", bg=C_BTN_OFF)
        self.status_var.set("Contacting APIs…")

        # Tell each card to dim while loading (keeps last known value visible)
        self.oil_card.loading()
        self.fx_card.loading()
        self.weather_card.loading()

        threading.Thread(target=self._fetch_in_background, daemon=True).start()


    def _fetch_in_background(self):
        """Runs on the background thread — one network call that gets all three."""
        result = fetch_and_save()
        self.after(0, lambda: self._update_display(result))


    def _update_display(self, result):
        """Runs back on the main thread — updates every card and the status bar."""
        oil     = result.get("oil_usd_per_barrel")
        rate    = result.get("usd_inr_rate")
        weather = result.get("weather") or {}
        ts      = result.get("timestamp", "")
        failures = 0

        # ── Oil card ──────────────────────────────────────────────────────────
        if oil is not None:
            self.oil_card.normal(f"${oil}", "")
        else:
            failures += 1
            reason = FETCH_ERRORS.get("oil", "Unknown error")
            soft   = reason is not None and "closed" in reason.lower()
            self.oil_card.error(reason, soft=soft)

        # ── FX card ───────────────────────────────────────────────────────────
        if rate is not None:
            self.fx_card.normal(f"{rate}", "")
        else:
            failures += 1
            reason = FETCH_ERRORS.get("fx", "Unknown error")
            soft   = reason is not None and "closed" in reason.lower()
            self.fx_card.error(reason, soft=soft)

        # ── Weather card ──────────────────────────────────────────────────────
        if weather:
            temp = weather.get("temp_c", "—")
            desc = weather.get("description", "").capitalize()
            hum  = weather.get("humidity_pct", "—")
            wind = weather.get("wind_kph", "—")
            self.weather_card.normal(str(temp),
                                     f"{desc}  ·  Humidity {hum}%  ·  Wind {wind} kph")
        else:
            failures += 1
            reason = FETCH_ERRORS.get("weather", "Unknown error")
            self.weather_card.error(reason)

        # ── Status bar ────────────────────────────────────────────────────────
        if failures == 0:
            self.status_var.set(f"✅  Saved at {ts}")
        elif failures == 3:
            self.status_var.set("❌  All sources failed — check internet connection")
        else:
            self.status_var.set(f"⚠   {failures} source(s) failed — see cards above  |  {ts}")

        # ── Re-enable button after cooldown ───────────────────────────────────
        # after(ms, fn) schedules fn to run after ms milliseconds on main thread
        self.after(COOLDOWN_MS, self._re_enable_button)


    def _re_enable_button(self):
        self.btn.config(text="  🔄  FETCH & SAVE  ", state="normal", bg=C_BTN)


    # ── UTILITY ───────────────────────────────────────────────────────────────

    def _center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = MonitorApp()
    app.mainloop()