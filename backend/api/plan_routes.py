"""API routes for the Local Life Planning Agent.

Primary endpoints (current main pipeline):
    POST /api/plan         — Main planning endpoint (V2 pipeline)
    POST /api/plan/stream  — Main streaming endpoint (SSE, V2 pipeline)

Compatibility endpoints (kept for backward compatibility):
    POST /api/plan/v2          — Same as /api/plan
    POST /api/plan/v2/stream   — Same as /api/plan/stream

Legacy (V1 mock pipeline, not the main demo flow):
    The V1 pipeline is preserved in backend/agent/orchestrator.py for reference.
    It is not exposed as a primary endpoint.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.agent.schemas import PlanRequest
from backend.agent.main_agent import run_local_life_agent, run_local_life_agent_stream

router = APIRouter()


# ── Primary endpoints ──────────────────────────────────────────────────


@router.post("/plan")
async def plan_route(request: PlanRequest):
    """Main planning endpoint — Local Life Agent pipeline (current V2)."""
    try:
        loc = request.location.model_dump() if request.location else None
        result = await run_local_life_agent(
            user_id=request.user_id,
            query=request.query,
            location=loc,
            demo_scenario=request.demo_scenario or "normal",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/plan/stream")
async def plan_route_stream(request: PlanRequest):
    """Main streaming endpoint — SSE events for real-time Agent progress."""
    loc = request.location.model_dump() if request.location else None

    async def event_stream():
        try:
            async for event_str in run_local_life_agent_stream(
                user_id=request.user_id,
                query=request.query,
                location=loc,
                demo_scenario=request.demo_scenario or "normal",
            ):
                yield event_str
        except Exception as e:
            import json
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Compatibility endpoints (keep existing integrations working) ───────


@router.post("/plan/v2")
async def plan_route_v2(request: PlanRequest):
    """Compatibility endpoint — delegates to /api/plan (V2 pipeline).

    Kept for backward compatibility with existing API consumers.
    Prefer /api/plan for new integrations.
    """
    return await plan_route(request)


@router.post("/plan/v2/stream")
async def plan_route_v2_stream(request: PlanRequest):
    """Compatibility endpoint — delegates to /api/plan/stream.

    Kept for backward compatibility with existing API consumers.
    Prefer /api/plan/stream for new integrations.
    """
    return await plan_route_stream(request)


# ── Provider status & mode endpoints ───────────────────────────────────


@router.get("/provider-status")
async def provider_status():
    """Get current provider mode status (basic)."""
    from backend.config.settings import get_settings
    settings = get_settings()
    return {
        "app_mode": settings.app_mode.value,
        "provider_status": settings.provider_status.to_dict(),
    }


@router.get("/provider/status")
async def provider_status_detailed():
    """Get detailed provider mode status for frontend display."""
    from backend.config.settings import get_settings
    settings = get_settings()
    ps = settings.provider_status.to_dict()
    return {
        "app_mode": settings.app_mode.value,
        "providers": ps,
        "safe_for_live_demo": settings.safe_for_live_demo,
        "execution_always_mock": True,
        "modes_available": {
            "demo_real": "真实API优先，mock兜底，execution始终mock",
            "demo_safe": "全部mock，稳定可控，适合比赛现场",
            "development": "开发模式，有key用真实无key用mock",
            "test": "测试模式，强制全部mock",
        },
    }


@router.get("/debug/amap-search")
async def debug_amap_search(city: str = "北京", keyword: str = "", poi_type: str = ""):
    """Debug endpoint: test AMap POI search directly in browser.

    Usage:
        /api/debug/amap-search?city=湖州
        /api/debug/amap-search?city=湖州&keyword=景点
        /api/debug/amap-search?city=沧州&poi_type=110000
    """
    from backend.providers.amap.factory import create_poi_provider
    provider = create_poi_provider()
    try:
        results = await provider.search_pois(
            keyword=keyword or None,
            city=city,
            poi_type=poi_type or None,
        )
        return {
            "city": city,
            "keyword": keyword or "(none)",
            "poi_type": poi_type or "(none)",
            "count": len(results),
            "results": [
                {
                    "name": r.get("name"),
                    "type": r.get("type"),
                    "address": r.get("address"),
                    "location": f"{r.get('longitude')}, {r.get('latitude')}",
                }
                for r in results[:20]
            ],
        }
    except Exception as e:
        return {"error": str(e), "city": city, "keyword": keyword}


@router.post("/mode/switch")
async def switch_mode(request: dict):
    """Switch app mode at runtime without restarting.

    Body: {"app_mode": "demo_real"} or {"app_mode": "demo_safe"}
    """
    from backend.config.settings import switch_app_mode, ConfigError
    new_mode = request.get("app_mode", "")
    if not new_mode:
        raise HTTPException(status_code=400, detail="Missing 'app_mode' in request body")
    try:
        settings = switch_app_mode(new_mode)
        return {
            "status": "ok",
            "app_mode": settings.app_mode.value,
            "providers": settings.provider_status.to_dict(),
            "safe_for_live_demo": settings.safe_for_live_demo,
        }
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
