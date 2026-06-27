import requests

# The shared error store. Keys match the three fetchers.
# Value is None when the last fetch succeeded, or a short string when it failed.
FETCH_ERRORS: dict = {"oil": None, "fx": None, "weather": None}


def classify_request_error(exc) -> str:
    
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "No internet connection"
    if isinstance(exc, requests.exceptions.Timeout):
        return "Connection timed out"
    if isinstance(exc, requests.exceptions.HTTPError):
        code = getattr(exc.response, "status_code", 0)
        if code == 401: return "Invalid API key (401)"
        if code == 429: return "Rate limited — try later (429)"
        if code >= 500: return f"Server error ({code})"
        return f"HTTP error ({code})"
    return f"Error: {str(exc)[:60]}"