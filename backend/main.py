"""FastAPI application entry point."""

import sys
import os
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api.plan_routes import router as plan_router
from backend.data_loader import load_all

app = FastAPI(
    title="Local Life Planning Agent",
    description="一句话安排本地生活短时活动，并自动完成预约/下单/发送消息",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan_router, prefix="/api")

# Serve the frontend build
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.on_event("startup")
async def startup():
    load_all()
    print("Data loaded successfully")


@app.get("/")
async def root():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Local Life Planning Agent API is running. Frontend not built — run: cd frontend && npm run build"}

