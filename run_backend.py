"""Backend server entry point.

Usage: python run_backend.py
Serves API + frontend on http://0.0.0.0:8000

Make sure the frontend is built first:
    cd frontend && npm run build
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from backend.data_loader import load_all

if __name__ == "__main__":
    load_all()
    print("Data loaded successfully")
    print("Starting Local Life Planning Agent on http://0.0.0.0:8000")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
