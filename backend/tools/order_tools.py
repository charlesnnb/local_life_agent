"""Order tools with unified return format."""

from backend.mock_api.order_api import (
    create_ticket_order as _create_ticket,
    create_restaurant_reservation as _create_resv,
    create_flower_or_cake_order as _create_extra,
    create_ride_order as _create_ride,
)


def create_ticket_order(
    poi_id: str,
    user_id: str,
    adult_count: int,
    child_count: int,
    time: str,
    total_price: float = 0,
) -> dict:
    """Create ticket order. Returns unified result dict."""
    try:
        result = _create_ticket(
            poi_id=poi_id,
            user_id=user_id,
            adult_count=adult_count,
            child_count=child_count,
            time_slot=time,
            total_price=total_price,
        )
        return {"success": True, "data": result, "error_code": None, "message": result["message"]}
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "ORDER_CREATE_ERROR", "message": str(e)}


def create_restaurant_reservation(
    restaurant_id: str,
    user_id: str,
    time: str,
    party_size: int,
    note: str = "",
) -> dict:
    """Create restaurant reservation. Returns unified result dict."""
    try:
        result = _create_resv(
            restaurant_id=restaurant_id,
            user_id=user_id,
            time=time,
            party_size=party_size,
            note=note,
        )
        return {"success": True, "data": result, "error_code": None, "message": result["message"]}
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "RESV_CREATE_ERROR", "message": str(e)}


def create_flower_or_cake_order(service_id: str, user_id: str, pickup_time: str) -> dict:
    """Create flower/cake order. Returns unified result dict."""
    try:
        result = _create_extra(
            service_id=service_id, user_id=user_id, pickup_time=pickup_time
        )
        return {"success": True, "data": result, "error_code": None, "message": result["message"]}
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "EXTRA_ORDER_ERROR", "message": str(e)}


def create_ride_order(user_id: str, from_loc: str, to_loc: str, departure_time: str) -> dict:
    """Create ride order. Returns unified result dict."""
    try:
        result = _create_ride(
            user_id=user_id,
            from_loc=from_loc,
            to_loc=to_loc,
            departure_time=departure_time,
        )
        return {"success": True, "data": result, "error_code": None, "message": result["message"]}
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "RIDE_ERROR", "message": str(e)}
