import tkinter as tk

# ── Visual tokens ─────────────────────────────────────────────────────────────
CARD    = "#1e293b"
TEXT    = "#f1f5f9"
MUTED   = "#64748b"
C_ERROR = "#ef4444"   # red
C_WARN  = "#f97316"   # orange (soft failure, e.g. markets closed)

F_CARD_HDR = ("Segoe UI",  8, "bold")
F_NUMBER   = ("Segoe UI", 34, "bold")
F_UNIT     = ("Segoe UI",  9)
F_SUB      = ("Segoe UI",  9)
F_BADGE    = ("Segoe UI",  7, "bold")


class DataCard(tk.Frame):
   
    def __init__(self, parent, title: str, unit: str, accent: str, col: int):
        super().__init__(parent, bg=CARD, padx=22, pady=0)
        self.grid(row=0, column=col, padx=(0 if col == 0 else 12), sticky="nsew")

        self._accent   = accent
        self._last_good = None   # remembers the last successful value

        # Top colour stripe
        self._stripe = tk.Frame(self, height=3, bg=accent)
        self._stripe.pack(fill="x")

        # Header row: title + "CACHED" / "STALE" badge
        hdr = tk.Frame(self, bg=CARD)
        hdr.pack(fill="x", pady=(14, 0))
        tk.Label(hdr, text=title, bg=CARD, fg=MUTED, font=F_CARD_HDR).pack(side="left")
        self._badge = tk.Label(hdr, text="", bg=CARD, fg=MUTED, font=F_BADGE)
        self._badge.pack(side="left", padx=(6, 0))

        # Big number
        self._num_var = tk.StringVar(value="—")
        self._num_lbl = tk.Label(self, textvariable=self._num_var,
                                 bg=CARD, fg=accent, font=F_NUMBER)
        self._num_lbl.pack(anchor="w", pady=(4, 0))

        # Unit label
        tk.Label(self, text=unit, bg=CARD, fg=MUTED, font=F_UNIT).pack(anchor="w")

        # Sub-line (weather description, or error reason)
        self._sub_var = tk.StringVar(value="")
        self._sub_lbl = tk.Label(self, textvariable=self._sub_var,
                                 bg=CARD, fg=TEXT, font=F_SUB,
                                 wraplength=200, justify="left")
        self._sub_lbl.pack(anchor="w", pady=(5, 0))

        tk.Frame(self, bg=CARD, height=18).pack()  # bottom padding

    # ── State methods ─────────────────────────────────────────────────────────

    def normal(self, value_str: str, sub: str = ""):
        """Display a successful value in the card's accent colour."""
        self._last_good = value_str
        self._stripe.config(bg=self._accent)
        self._num_lbl.config(fg=self._accent)
        self._num_var.set(value_str)
        self._sub_var.set(sub)
        self._sub_lbl.config(fg=TEXT)
        self._badge.config(text="")

    def loading(self):
        """Dim while fetching; keep the last known value visible."""
        self._stripe.config(bg=MUTED)
        self._num_lbl.config(fg=MUTED)
        if self._last_good:
            self._num_var.set(self._last_good)
            self._badge.config(text="CACHED")
        else:
            self._num_var.set("…")
            self._badge.config(text="")
        self._sub_var.set("")

    def error(self, reason: str = "", soft: bool = False):
        """
        Show failure state.
        soft=True  → orange (e.g. markets closed — expected downtime)
        soft=False → red   (real error: no internet, bad key, etc.)
        """
        colour = C_WARN if soft else C_ERROR
        self._stripe.config(bg=colour)
        self._num_lbl.config(fg=colour)
        if self._last_good:
            self._num_var.set(self._last_good)
            self._badge.config(text="STALE")
        else:
            self._num_var.set("—")
            self._badge.config(text="")
        self._sub_var.set(reason or "Could not retrieve data")
        self._sub_lbl.config(fg=colour)