"""API routes for the planning agent."""

from fastapi import APIRouter, HTTPException
from backend.agent.schemas import PlanRequest
from backend.agent.orchestrator import run_local_life_agent
from backend.agent.orchestrator_v2 import run_agent_v2

router = APIRouter()


@router.post("/plan")
async def plan_route(request: PlanRequest):
    """Main planning endpoint — legacy v1 orchestrator."""
    try:
        result = run_local_life_agent(
            user_id=request.user_id,
            query=request.query,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/plan/v2")
async def plan_route_v2(request: PlanRequest):
    """Main planning endpoint — v2 orchestrator with provider abstraction."""
    try:
        result = await run_agent_v2(
            user_id=request.user_id,
            query=request.query,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.get("/provider-status")
async def provider_status():
    """Get current provider mode status."""
    from backend.config.settings import get_settings
    settings = get_settings()
    return {
        "app_mode": settings.app_mode.value,
        "provider_status": settings.provider_status.to_dict(),
    }
