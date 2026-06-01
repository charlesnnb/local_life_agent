"""Ticket tools with unified return format."""

from backend.mock_api.ticket_api import check_ticket_availability as _check_tickets


def check_ticket_availability(
    poi_id: str,
    date: str = "2026-06-01",
    adult_count: int = 2,
    child_count: int = 0,
    preferred_time: str | None = None,
) -> dict:
    """Check ticket availability. Returns unified result dict."""
    try:
        result = _check_tickets(
            poi_id=poi_id,
            date=date,
            adult_count=adult_count,
            child_count=child_count,
            preferred_time=preferred_time,
        )
        return {
            "success": True,
            "data": result,
            "error_code": None,
            "message": f"有票，剩余 {result.get('remaining', 0)} 张，总价 ¥{result.get('total_price', 0)}"
            if result.get("available")
            else result.get("reason", "票务不足"),
        }
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "TICKET_ERROR", "message": str(e)}
