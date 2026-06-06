"""Deterministic mock commerce fields for real AMap place records."""

import hashlib

from src.schemas.models import UserIntent


def enrich_activity(
    place: dict,
    intent: UserIntent,
    search_query: str,
) -> dict:
    """Add planning fields that public map search does not provide."""
    seed = _seed(place.get("id") or place.get("name") or search_query)
    place_text = " ".join(
        [
            str(place.get("name", "")),
            str(place.get("type", "")),
        ]
    ).lower()
    query_text = search_query.lower()
    child_friendly = any(
        word in place_text
        for word in ["亲子", "儿童", "乐园", "科普", "kids"]
    ) or (
        any(word in query_text for word in ["亲子", "儿童"])
        and seed % 4 != 0
    )
    indoor = not any(
        word in place_text
        for word in ["公园", "户外", "citywalk", "街区", "步道"]
    )
    tags = ["amap_real_place"]
    if indoor:
        tags.append("indoor")
    else:
        tags.append("outdoor")
    if child_friendly:
        tags.extend(["kids", "family", "educational"])
    if any(word in place_text for word in ["展览", "博物", "美术", "科普"]):
        tags.extend(["exhibition", "educational"])
    if any(word in place_text for word in ["citywalk", "街区", "步行"]):
        tags.extend(["citywalk", "historic", "photo_friendly"])

    return {
        **place,
        "id": f"amap_{place.get('id') or seed}",
        "source": "amap",
        "tags": list(dict.fromkeys(tags)),
        "suitable_scenes": [intent.scene],
        "age_range": [0, 99] if child_friendly else [6, 99],
        "avg_duration_min": 90,
        "rating": place.get("rating") or round(4.1 + seed % 7 / 10, 1),
        "price": 40 + seed % 100,
        "indoor": indoor,
        "wait_time_min": 5 + seed % 16,
        "child_friendly": child_friendly,
    }


def enrich_restaurant(
    place: dict,
    intent: UserIntent,
    search_query: str,
) -> dict:
    """Add mock transaction fields while preserving the real map identity."""
    seed = _seed(place.get("id") or place.get("name") or search_query)
    place_text = " ".join(
        [
            str(place.get("name", "")),
            str(place.get("type", "")),
        ]
    ).lower()
    query_text = search_query.lower()
    diet_friendly = any(
        word in place_text
        for word in ["轻食", "健康", "清淡", "素食", "沙拉", "低脂"]
    ) or (
        any(
            word in query_text
            for word in ["轻食", "健康", "清淡", "素食", "低脂"]
        )
        and seed % 3 == 0
    )
    child_friendly = any(
        word in place_text for word in ["亲子", "儿童", "家庭"]
    ) or (
        intent.scene == "family" and seed % 2 == 0
    )
    tags = ["amap_real_place"]
    if diet_friendly:
        tags.extend(["healthy", "light_food", "low_fat"])
    if child_friendly:
        tags.extend(["family_friendly", "kids_friendly"])
    if any(word in place_text for word in ["网红", "咖啡", "西餐"]):
        tags.append("photo_friendly")
    if "火锅" in place_text:
        tags.extend(["hotpot", "spicy"])

    avg_price = place.get("cost")
    if not isinstance(avg_price, (int, float)) or avg_price <= 0:
        avg_price = 60 + seed % 81
    return {
        **place,
        "id": f"amap_rest_{place.get('id') or seed}",
        "source": "amap",
        "tags": list(dict.fromkeys(tags)),
        "suitable_scenes": [intent.scene],
        "avg_price": round(float(avg_price)),
        "rating": place.get("rating") or round(4.1 + seed % 7 / 10, 1),
        "wait_time_min": 5 + seed % 16,
        "reservation_supported": seed % 4 != 0,
        "reservation_available": seed % 4 != 0,
        "has_low_fat_meal": diet_friendly,
        "diet_friendly": diet_friendly,
        "has_kids_meal": child_friendly,
        "child_friendly": child_friendly,
    }


def _seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)
