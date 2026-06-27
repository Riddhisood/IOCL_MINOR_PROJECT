# IOCL_MINOR_PROJECT

# Market & Weather Monitor (IOCL Minor Project)

A clean, modular desktop application built with Python and Tkinter that fetches real-time market indices (WTI Crude Oil, USD/INR Forex rate) and weather metrics for Delhi, India. The application persists snapshot data locally in both JSON and CSV formats for historical logging and data tracking.

## Features
- **Real-Time Data Fetching:** Instantly retrieves WTI Crude Oil prices and USD/INR exchange rates via Yahoo Finance (`yfinance`), alongside current weather conditions via the OpenWeatherMap API.
- **Robust Local Storage:** Automatically logs data into two structures inside the `data_logs/` directory:
  - `snapshot_[timestamp].json`: Detailed multi-source structural snapshot.
  - `running_log.csv`: Continuous append-only file ideal for trends or importing into Excel.
- **Dynamic UI States:** Custom Tkinter data cards reflect normal operations, background loading buffers ("Cached"), and granular visual error indicators ("Stale").
- **Threaded Execution:** Fetch operations run on asynchronous background threads to keep the desktop interface fluid and prevent application freezing.

## Project Structure
The repository is strictly isolated by functional responsibilities to prevent tight coupling and circular dependencies:

```text
IOCL_MINOR_PROJECT/
│   main.py               # Entry point of the application
│   .env                  # Private API keys (Git ignored)
│   requirements.txt      # Dependency checklist
│
├───config/
│       settings.py       # Single source of truth for global configurations
│
├───core/
│       errors.py         # Neutral store for error statuses across modules
│       saver.py          # Disk persistence engine (JSON and CSV)
│
├───fetchers/
│       forex.py          # API handler for currency exchange tracking
│       oil.py            # API handler for WTI crude metrics
│       weather.py        # API handler for OpenWeatherMap endpoints
│
└───gui/
        app.py            # Base window layouts, thread dispatching & lifecycle
        widgets.py        # Custom styled UI interface components (Data Cards)

