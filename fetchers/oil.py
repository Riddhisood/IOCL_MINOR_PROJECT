import yfinance as yf
from core.errors import FETCH_ERRORS


def get_crude_oil_price() -> float | None:
    
    FETCH_ERRORS["oil"] = None  # clear any previous error

    try:
        ticker = yf.Ticker("CL=F")

        # PRIMARY: live quote
        price = ticker.fast_info.get("last_price") or ticker.fast_info.get("lastPrice")
        if price and float(price) > 0:
            return round(float(price), 2)

        # FALLBACK: most recent 1-minute bar
        intraday = ticker.history(period="1d", interval="1m")
        if not intraday.empty:
            return round(float(intraday["Close"].iloc[-1]), 2)

        FETCH_ERRORS["oil"] = "Markets closed / no data"
        return None

    except Exception as exc:
        err = str(exc).lower()
        if "connection" in err or "network" in err or "failed to get" in err:
            FETCH_ERRORS["oil"] = "No internet connection"
        elif "json" in err:
            FETCH_ERRORS["oil"] = "Bad data from Yahoo Finance"
        else:
            FETCH_ERRORS["oil"] = f"Error: {str(exc)[:60]}"
        return None