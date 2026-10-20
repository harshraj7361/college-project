"""
run.py - One-Click Launcher for PDF Notes Generator
----------------------------------------------------
Usage:
    python run.py

This script starts the FastAPI development server and serves both
the backend endpoints and the frontend web user interface.
"""

import sys
import webbrowser
import threading
import time


def open_browser():
    """Wait 1.5 seconds for the server to bind, then open the browser automatically."""
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"\n🚀 Opening web browser to {url} ...\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    print("=" * 60)
    print("      PDF NOTES GENERATOR - College Minor Project")
    print("=" * 60)
    print("Starting FastAPI Backend & Web Interface...")
    print("API & UI URL:  http://127.0.0.1:8000")
    print("API Docs:      http://127.0.0.1:8000/docs")
    print("Press CTRL+C to stop the server.")
    print("=" * 60)

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Import and run uvicorn
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
