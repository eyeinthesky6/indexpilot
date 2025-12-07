#!/usr/bin/env python3
"""Run IndexPilot API Server

Starts the FastAPI server for the dashboard UI.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )

