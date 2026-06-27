import yfinance as yf
from core.errors import FETCH_ERRORS


def get_usd_inr_rate() -> float | None:
 
    FETCH_ERRORS["fx"] = None

    try:
        ticker = yf.Ticker("USDINR=X")

        price = ticker.fast_info.get("last_price") or ticker.fast_info.get("lastPrice")
        if price and float(price) > 0:
            return round(float(price), 4)

        intraday = ticker.history(period="1d", interval="1m")
        if not intraday.empty:
            return round(float(intraday["Close"].iloc[-1]), 4)

        FETCH_ERRORS["fx"] = "Markets closed / no data"
        return None

    except Exception as exc:
        err = str(exc).lower()
        if "connection" in err or "network" in err or "failed to get" in err:
            FETCH_ERRORS["fx"] = "No internet connection"
        else:
            FETCH_ERRORS["fx"] = f"Error: {str(exc)[:60]}"
        return None