"""FastAPI application for the Local Life Agent MVP."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.agents.planner_agent import PlannerAgent
from src.config.settings import settings
from src.schemas.models import (
    PlanEvent,
    PlanRequest,
    PlanResponse,
    PreferenceProfile,
    PreferenceSetup,
    ReplanConfirmRequest,
    RuntimeMode,
    UserPreference,
)
from src.core.replan_service import apply_replan
from src.services.preference_service import (
    get_current_profile,
    get_default_setup,
    save_preference,
)


app = FastAPI(
    title="Local Life Agent",
    description="一句话生成可直接执行的本地活动方案",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = PlannerAgent()
frontend_dist = settings.frontend_dist
assets_dir = frontend_dist / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/api/runtime", response_model=RuntimeMode)
def get_runtime_mode() -> RuntimeMode:
    """Expose presentation-safe provider mode metadata to the frontend."""
    mode = settings.run_mode
    llm = (
        "mock"
        if (
            mode == "demo"
            or settings.demo_mode
            or settings.use_mock_llm
            or not settings.enable_llm
            or not settings.deepseek_api_key
        )
        else "deepseek"
    )
    amap = (
        "mock"
        if (
            mode == "demo"
            or settings.demo_mode
            or settings.use_mock_amap
            or not settings.enable_amap
            or not settings.amap_api_key
        )
        else "amap"
    )
    actions = (
        "mock"
        if settings.use_mock_actions or mode in {"demo", "hybrid"}
        else "mock_fallback"
    )
    return RuntimeMode(
        mode=mode,
        llm=llm,
        amap=amap,
        actions=actions,
    )


@app.get(
    "/api/preferences/default",
    response_model=PreferenceSetup,
)
def get_default_preferences() -> PreferenceSetup:
    """Return questionnaire options and the default profile."""
    return get_default_setup()


@app.post(
    "/api/preferences",
    response_model=PreferenceProfile,
)
def update_preferences(
    preference: UserPreference,
) -> PreferenceProfile:
    """Store the current demo user's preference profile in memory."""
    return save_preference(preference)


@app.get(
    "/api/preferences/current",
    response_model=PreferenceProfile,
)
def get_preferences() -> PreferenceProfile:
    """Return the active in-memory profile and normalized weights."""
    return get_current_profile()


@app.post("/api/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest) -> PlanResponse:
    """Generate and execute a complete mock local-life plan."""
    try:
        return planner.run(request.query, request.location)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/replan/confirm", response_model=PlanResponse)
def confirm_replan(request: ReplanConfirmRequest) -> PlanResponse:
    """Apply one explicitly confirmed option to the submitted current plan."""
    try:
        return apply_replan(
            request.current_plan,
            request.proposal_id,
            request.option_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plan/stream")
async def stream_plan(request: PlanRequest) -> StreamingResponse:
    """Stream planner progress as SSE and finish with the full response."""

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[PlanEvent | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: PlanEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def execute_plan() -> None:
            try:
                result = await asyncio.to_thread(
                    planner.run,
                    request.query,
                    request.location,
                    emit,
                )
                queue.put_nowait(
                    PlanEvent(
                        type="result",
                        stage="completed",
                        message="方案生成完成",
                        data=result.model_dump(mode="json"),
                    )
                )
            except Exception as exc:
                queue.put_nowait(
                    PlanEvent(
                        type="error",
                        stage="failed",
                        message=str(exc) or "方案生成失败",
                    )
                )
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(execute_plan())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
def root():
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "Local Life Agent API is running.",
        "endpoints": [
            "GET /api/runtime",
            "GET /api/preferences/default",
            "POST /api/preferences",
            "GET /api/preferences/current",
            "POST /api/plan",
            "POST /api/plan/stream",
            "POST /api/replan/confirm",
        ],
    }


@app.get("/settings", include_in_schema=False)
def settings_page():
    """Serve the React Router settings page from the production build."""
    return root()
