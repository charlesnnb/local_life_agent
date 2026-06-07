"""Consent and full-plan update coverage for replan confirmation."""

import asyncio
import copy

import httpx
import pytest

from src.app import app
from src.agents.planner_agent import PlannerAgent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider

from test_exception_handling import _plan_and_tool_results


def _proposal_for(scenario: str):
    try:
        from src.core.exception_detector import detect_exceptions
        from src.core.replan_service import build_replan_proposals
    except ModuleNotFoundError:
        pytest.fail("replan service is not implemented")

    plan, tool_results = _plan_and_tool_results()
    if scenario == "restaurant_full":
        reservation = next(
            action for action in plan.actions if action.type == "reservation"
        )
        reservation.status = "mock_failed"
        reservation.details = {
            "reason": "restaurant_full",
            "requested_time": reservation.details.get("time", "18:00"),
        }
    if scenario == "traffic_delay":
        reservation = next(
            action for action in plan.actions if action.type == "reservation"
        )
        restaurant_item = next(
            item for item in plan.timeline.items if item.type == "restaurant"
        )
        reservation.details["time"] = restaurant_item.time

    exceptions = detect_exceptions(
        plan,
        tool_results,
        scenario=scenario,
        traffic_delay_minutes=25,
    )
    proposals = build_replan_proposals(plan, exceptions, tool_results)
    plan.exceptions = exceptions
    plan.replan_proposals = proposals
    return plan, proposals[0]


def _apply_replan():
    try:
        from src.core.replan_service import apply_replan
    except ModuleNotFoundError:
        pytest.fail("replan service is not implemented")
    return apply_replan


def test_confirming_restaurant_replacement_updates_full_plan():
    apply_replan = _apply_replan()
    plan, proposal = _proposal_for("restaurant_full")
    option = next(
        item
        for item in proposal.options
        if item.operation == "replace_restaurant"
    )
    old_name = next(
        stop.name for stop in plan.route.stops if stop.type == "restaurant"
    )
    old_route_minutes = plan.route.total_travel_minutes

    updated = apply_replan(plan, proposal.proposal_id, option.option_id)

    assert updated is not plan
    assert updated.route.total_travel_minutes >= old_route_minutes
    assert next(
        stop.name for stop in updated.route.stops if stop.type == "restaurant"
    ) == "海底捞徐家汇店"
    assert old_name not in " ".join(
        f"{item.title} {item.description}" for item in updated.timeline.items
    )
    reservation = next(
        action for action in updated.actions if action.type == "reservation"
    )
    assert reservation.target == "海底捞徐家汇店"
    assert reservation.status == "mock_success"
    message = next(
        action for action in updated.actions if action.type == "send_message"
    )
    assert "海底捞徐家汇店" in (message.message or "")
    assert updated.replan_proposals[0].status == "accepted"
    assert updated.exceptions[0].status == "resolved"


def test_confirming_activity_replacement_updates_route_and_timeline():
    apply_replan = _apply_replan()
    plan, proposal = _proposal_for("activity_unavailable")
    option = next(
        item
        for item in proposal.options
        if item.operation == "replace_activity"
    )

    updated = apply_replan(plan, proposal.proposal_id, option.option_id)

    assert next(
        stop.name for stop in updated.route.stops if stop.type == "activity"
    ) == "徐汇儿童科学体验展"
    assert "徐汇儿童科学体验展" in " ".join(
        f"{item.title} {item.description}" for item in updated.timeline.items
    )
    assert "徐汇儿童科学体验展" in next(
        action.message or ""
        for action in updated.actions
        if action.type == "send_message"
    )


def test_confirming_traffic_adjustment_updates_route_timeline_and_reservation():
    apply_replan = _apply_replan()
    plan, proposal = _proposal_for("traffic_delay")
    option = next(
        item
        for item in proposal.options
        if item.operation == "adjust_reservation"
    )
    before_route_minutes = plan.route.total_travel_minutes
    before_times = [item.time for item in plan.timeline.items]

    updated = apply_replan(plan, proposal.proposal_id, option.option_id)

    assert updated.route.total_travel_minutes == before_route_minutes + 25
    assert [item.time for item in updated.timeline.items] != before_times
    reservation = next(
        action for action in updated.actions if action.type == "reservation"
    )
    assert reservation.status == "mock_success"
    assert reservation.details["time"] == option.metadata["new_time"]
    assert "交通延误" in (reservation.message or "")


def test_keep_original_does_not_modify_operational_plan():
    apply_replan = _apply_replan()
    plan, proposal = _proposal_for("restaurant_full")
    option = next(
        item for item in proposal.options if item.operation == "keep_original"
    )
    before = copy.deepcopy(
        {
            "plan": plan.plan.model_dump(mode="json"),
            "route": plan.route.model_dump(mode="json"),
            "timeline": plan.timeline.model_dump(mode="json"),
            "actions": [
                action.model_dump(mode="json") for action in plan.actions
            ],
            "composition": (
                plan.composition.model_dump(mode="json")
                if plan.composition
                else None
            ),
        }
    )

    updated = apply_replan(plan, proposal.proposal_id, option.option_id)

    after = {
        "plan": updated.plan.model_dump(mode="json"),
        "route": updated.route.model_dump(mode="json"),
        "timeline": updated.timeline.model_dump(mode="json"),
        "actions": [
            action.model_dump(mode="json") for action in updated.actions
        ],
        "composition": (
            updated.composition.model_dump(mode="json")
            if updated.composition
            else None
        ),
    }
    assert after == before
    assert updated.replan_proposals[0].status == "kept"
    assert updated.exceptions[0].status == "acknowledged"
    assert any("保留原计划" in warning for warning in updated.planning_warnings)


def test_confirmation_endpoint_returns_updated_plan():
    plan, proposal = _proposal_for("restaurant_full")
    option = next(
        item
        for item in proposal.options
        if item.operation == "replace_restaurant"
    )

    async def post_confirmation():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/replan/confirm",
                json={
                    "current_plan": plan.model_dump(mode="json"),
                    "proposal_id": proposal.proposal_id,
                    "option_id": option.option_id,
                },
            )

    response = asyncio.run(post_confirmation())

    assert response.status_code == 200
    payload = response.json()
    assert payload["replan_proposals"][0]["status"] == "accepted"
    assert any(
        stop["name"] == "海底捞徐家汇店"
        for stop in payload["route"]["stops"]
    )


def test_explicit_reservation_time_matches_confirmed_traffic_timeline(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_SCENARIO", "traffic_delay")
    planner = PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )
    plan = planner.run("下午去展览，16:30 预约餐厅吃饭")
    proposal = plan.replan_proposals[0]
    option = next(
        item
        for item in proposal.options
        if item.operation == "adjust_reservation"
    )

    updated = _apply_replan()(
        plan,
        proposal.proposal_id,
        option.option_id,
    )

    restaurant_item = next(
        item for item in updated.timeline.items if item.type == "restaurant"
    )
    assert restaurant_item.time == option.proposed_plan["arrival"]
