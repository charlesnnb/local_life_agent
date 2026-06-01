"""Message tools with unified return format."""

from backend.mock_api.order_api import send_plan_message as _send
from backend.mock_api.message_api import search_services as _search_services


def search_services(
    nearby_location: str | None = None,
    service_type: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Search extra services (cake, flower, coffee, dessert)."""
    try:
        results = _search_services(
            nearby_location=nearby_location,
            service_type=service_type,
            tags=tags,
        )
        return {
            "success": True,
            "data": results,
            "error_code": None,
            "message": f"找到 {len(results)} 个服务" if results else "未找到匹配的服务",
        }
    except Exception as e:
        return {"success": False, "data": [], "error_code": "SERVICE_ERROR", "message": str(e)}


def send_plan_message(
    user_id: str,
    to: str = "家人",
    channel: str = "wechat",
    message: str = "",
) -> dict:
    """Send plan message. Returns unified result dict."""
    try:
        result = _send(user_id=user_id, to=to, channel=channel, message=message)
        return {
            "success": True,
            "data": result,
            "error_code": None,
            "message": "消息已发送",
        }
    except Exception as e:
        return {
            "success": False,
            "data": {"sent": False, "message": message},
            "error_code": "MESSAGE_ERROR",
            "message": f"发送失败，可复制文本手动发送: {str(e)}",
        }
