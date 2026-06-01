"""Mock Ticket API — check ticket availability and pricing."""

from backend.data_loader import get_tickets


def check_ticket_availability(
    poi_id: str,
    date: str = "2026-06-01",
    adult_count: int = 2,
    child_count: int = 0,
    preferred_time: str | None = None,
) -> dict:
    """Check if tickets are available for a POI at given date/time."""
    for t in get_tickets():
        if t["poi_id"] == poi_id and t["date"] == date:
            total_needed = adult_count + child_count
            if t["remaining"] >= total_needed:
                adult_price_total = adult_count * t["adult_price"]
                child_price_total = child_count * t["child_price"]
                total_price = adult_price_total + child_price_total

                slots = t.get("time_slots", [])
                suggested = preferred_time
                if preferred_time and preferred_time not in slots:
                    # Find nearest available slot
                    suggested = None
                    for s in slots:
                        if s >= (preferred_time or ""):
                            suggested = s
                            break
                    if not suggested and slots:
                        suggested = slots[-1]

                return {
                    "available": True,
                    "remaining": t["remaining"],
                    "total_price": total_price,
                    "adult_price": t["adult_price"],
                    "child_price": t["child_price"],
                    "time_slots": slots,
                    "suggested_time_slot": suggested or (slots[0] if slots else None),
                }
            else:
                return {
                    "available": False,
                    "remaining": t["remaining"],
                    "total_price": 0,
                    "time_slots": t.get("time_slots", []),
                    "suggested_time_slots": t.get("time_slots", []),
                    "reason": f"仅剩 {t['remaining']} 张票，需要 {total_needed} 张",
                }

    return {
        "available": False,
        "remaining": 0,
        "total_price": 0,
        "time_slots": [],
        "suggested_time_slots": [],
        "reason": "该POI无票务信息",
    }
