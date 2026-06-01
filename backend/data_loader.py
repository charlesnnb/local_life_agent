"""Data loader: reads all JSON mock data files into memory at startup."""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_cache: dict[str, any] = {}


def _load_json(filename: str) -> dict | list:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all() -> dict[str, any]:
    """Load all data files into the in-memory cache and return as a dict."""
    global _cache
    _cache = {
        "users": _load_json("users.json"),
        "family_profiles": _load_json("family_profiles.json"),
        "friend_groups": _load_json("friend_groups.json"),
        "pois": _load_json("pois.json"),
        "restaurants": _load_json("restaurants.json"),
        "availability": _load_json("availability.json"),
        "tickets": _load_json("tickets.json"),
        "travel_times": _load_json("travel_times.json"),
        "services": _load_json("services.json"),
        "orders": _load_json("orders.json"),
    }
    return _cache


def get_data(key: str):
    """Get a specific dataset from cache."""
    if key not in _cache:
        data = _load_json(f"{key}.json")
        _cache[key] = data
    return _cache[key]


def get_users() -> list[dict]:
    return get_data("users").get("users", [])


def get_user(user_id: str) -> dict | None:
    for u in get_users():
        if u["user_id"] == user_id:
            return u
    return None


def get_family_profile(user_id: str) -> dict | None:
    for p in get_data("family_profiles").get("profiles", []):
        if p["user_id"] == user_id:
            return p
    return None


def get_friend_group(group_id: str) -> dict | None:
    for g in get_data("friend_groups").get("groups", []):
        if g["group_id"] == group_id:
            return g
    return None


def get_pois() -> list[dict]:
    return get_data("pois").get("pois", [])


def get_restaurants() -> list[dict]:
    return get_data("restaurants").get("restaurants", [])


def get_availability() -> list[dict]:
    return get_data("availability").get("availability", [])


def get_tickets() -> list[dict]:
    return get_data("tickets").get("tickets", [])


def get_travel_times() -> list[dict]:
    return get_data("travel_times").get("travel_times", [])


def get_services() -> list[dict]:
    return get_data("services").get("services", [])


def get_orders() -> list[dict]:
    return get_data("orders").get("orders", [])
