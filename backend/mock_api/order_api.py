"""Mock Order API — create mock orders (tickets, reservations, rides, services)."""

import uuid
import random
from datetime import datetime


def _gen_id(prefix: str) -> str:
    short = uuid.uuid4().hex[:8].upper()
    return f"{prefix}_{short}"


def create_ticket_order(
    poi_id: str,
    user_id: str,
    adult_count: int,
    child_count: int,
    time_slot: str,
    total_price: float,
) -> dict:
    """Create a mock ticket order."""
    order_id = _gen_id("TKT")
    return {
        "order_id": order_id,
        "poi_id": poi_id,
        "user_id": user_id,
        "adult_count": adult_count,
        "child_count": child_count,
        "time_slot": time_slot,
        "total_price": total_price,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "message": f"门票订单已确认，订单号 {order_id}",
    }


def create_restaurant_reservation(
    restaurant_id: str,
    user_id: str,
    time: str,
    party_size: int,
    note: str = "",
) -> dict:
    """Create a mock restaurant reservation."""
    resv_id = _gen_id("RESV")
    return {
        "reservation_id": resv_id,
        "restaurant_id": restaurant_id,
        "user_id": user_id,
        "time": time,
        "party_size": party_size,
        "note": note,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "message": f"餐厅预约已确认，预约号 {resv_id}",
    }


def create_flower_or_cake_order(
    service_id: str,
    user_id: str,
    pickup_time: str,
) -> dict:
    """Create a mock flower/cake order."""
    order_id = _gen_id("CAKE")
    return {
        "order_id": order_id,
        "service_id": service_id,
        "user_id": user_id,
        "pickup_time": pickup_time,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "message": f"额外服务订单已确认，订单号 {order_id}",
    }


def create_ride_order(
    user_id: str,
    from_loc: str,
    to_loc: str,
    departure_time: str,
) -> dict:
    """Create a mock ride (taxi) order."""
    ride_id = _gen_id("RIDE")
    estimated_price = round(random.uniform(18, 45), 2)
    return {
        "ride_id": ride_id,
        "user_id": user_id,
        "from": from_loc,
        "to": to_loc,
        "departure_time": departure_time,
        "estimated_price": estimated_price,
        "driver_status": "assigned",
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "message": f"打车订单已确认，预计 ¥{estimated_price}，订单号 {ride_id}",
    }


def send_plan_message(
    user_id: str,
    to: str,
    channel: str,
    message: str,
) -> dict:
    """Mock sending a plan message."""
    msg_id = _gen_id("MSG")
    return {
        "sent": True,
        "message_id": msg_id,
        "to": to,
        "channel": channel,
        "message": message,
        "created_at": datetime.now().isoformat(),
        "status": "delivered",
    }
