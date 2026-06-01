"""Mock Message API — message sending operations."""

from backend.data_loader import get_services


def search_services(
    nearby_location: str | None = None,
    service_type: str | None = None,
    tags: list[str] | None = None,
) -> list[dict]:
    """Search available services (cake, flower, coffee, dessert)."""
    results = []
    for s in get_services():
        if not s.get("available", False):
            continue
        if service_type and s.get("type") != service_type:
            continue
        if nearby_location and nearby_location not in s.get("nearby", []):
            continue
        if tags:
            s_tags = set(s.get("tags", []))
            if not s_tags.intersection(tags):
                continue
        results.append(s)
    return results
