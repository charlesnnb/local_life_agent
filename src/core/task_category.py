"""Lightweight task category normalization shared across POI execution."""

from typing import Literal

from src.schemas.models import PlannedTask


TaskCategory = Literal[
    "playground",
    "park",
    "billiards",
    "tea_house",
    "tea_drink",
    "bar",
    "mountain_hiking",
    "fishing",
    "trampoline",
    "restaurant",
    "cafe",
    "hotel_lounge",
    "food_delivery",
    "unknown",
]


CATEGORY_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "playground": {
        "task_terms": ("游乐场", "儿童乐园", "亲子乐园"),
        "positive": (
            "游乐场",
            "儿童乐园",
            "亲子乐园",
            "乐园",
            "playground",
            "kids",
            "family",
        ),
        "negative": ("餐厅", "酒店", "培训", "健身房"),
    },
    "park": {
        "task_terms": ("公园", "小花园", "绿地", "体育公园", "滨江步道"),
        "positive": (
            "公园",
            "花园",
            "小花园",
            "绿地",
            "森林",
            "广场",
            "步道",
            "滨江",
            "体育公园",
            "湿地",
            "口袋公园",
        ),
        "negative": ("餐厅", "酒店", "培训", "商场", "健身房"),
    },
    "billiards": {
        "task_terms": ("打台球", "台球", "台球馆", "桌球", "九球"),
        "positive": (
            "台球",
            "桌球",
            "九球",
            "球房",
            "台球俱乐部",
            "桌球俱乐部",
            "自助台球",
            "billiard",
            "pool",
        ),
        "negative": ("游泳", "健身", "培训", "餐厅", "酒店", "ktv"),
    },
    "tea_house": {
        "task_terms": ("喝茶", "茶馆", "茶室", "茶楼", "茶客厅"),
        "positive": (
            "茶馆",
            "茶室",
            "茶楼",
            "茶社",
            "茶舍",
            "茶空间",
            "茶客厅",
            "茗茶",
            "棋牌茶室",
            "喝茶",
            "茶",
        ),
        "negative": ("酒吧", "夜店", "ktv", "酒店住宿"),
    },
    "tea_drink": {
        "task_terms": ("霸王茶姬", "茶饮", "奶茶"),
        "positive": (
            "霸王茶姬",
            "茶饮",
            "奶茶",
            "茶姬",
            "tea",
            "milk tea",
        ),
        "negative": ("酒吧", "餐厅", "酒店", "培训"),
    },
    "mountain_hiking": {
        "task_terms": ("爬山", "登山", "森林公园", "郊野公园", "登山步道"),
        "positive": (
            "山",
            "登山",
            "爬山",
            "森林公园",
            "郊野公园",
            "步道",
            "风景区",
            "自然风景",
        ),
        "negative": ("游泳", "健身", "培训", "餐饮", "商场", "酒店", "ktv"),
    },
    "fishing": {
        "task_terms": ("钓鱼", "垂钓"),
        "positive": ("钓鱼", "垂钓", "鱼塘", "湖", "水库", "垂钓园"),
        "negative": ("餐饮", "商场", "培训", "酒店"),
    },
    "trampoline": {
        "task_terms": ("蹦床", "trampoline"),
        "positive": ("蹦床", "trampoline", "蹦床馆", "运动公园"),
        "negative": ("餐饮", "商场", "酒店", "培训"),
    },
    "hotel_lounge": {
        "task_terms": (
            "高档酒店",
            "五星级",
            "酒店酒廊",
            "大堂吧",
            "行政酒廊",
        ),
        "positive": (
            "酒店",
            "五星级",
            "高档",
            "大堂吧",
            "酒廊",
            "lounge",
            "行政酒廊",
        ),
        "negative": ("快捷酒店", "旅馆", "招待所"),
    },
    "bar": {
        "task_terms": ("酒吧", "清吧", "小酒馆", "pub", "bar"),
        "positive": (
            "酒吧",
            "清吧",
            "小酒馆",
            "pub",
            "bar",
            "lounge",
            "鸡尾酒",
        ),
        "negative": ("茶室", "茶楼", "培训", "酒店住宿"),
    },
    "restaurant": {
        "task_terms": (
            "餐厅",
            "吃饭",
            "川菜",
            "火锅",
            "日料",
            "烧烤",
            "粤菜",
            "西餐",
            "轻食",
            "聚餐",
        ),
        "positive": (
            "餐厅",
            "饭店",
            "火锅",
            "川菜",
            "日料",
            "粤菜",
            "烧烤",
            "西餐",
            "轻食",
            "聚餐",
            "吃饭",
        ),
        "negative": (),
    },
    "cafe": {
        "task_terms": ("喝咖啡", "咖啡店", "咖啡", "cafe", "coffee"),
        "positive": ("咖啡", "咖啡店", "cafe", "coffee"),
        "negative": (),
    },
}


CATEGORY_LABELS: dict[str, str] = {
    "playground": "游乐场",
    "park": "公园",
    "billiards": "台球",
    "tea_house": "茶馆",
    "tea_drink": "茶饮",
    "bar": "酒吧",
    "mountain_hiking": "爬山",
    "fishing": "钓鱼",
    "trampoline": "蹦床",
    "restaurant": "餐厅",
    "cafe": "咖啡",
    "hotel_lounge": "酒店/酒廊",
    "food_delivery": "外卖",
    "unknown": "活动",
}


def normalize_task_category(task: PlannedTask) -> TaskCategory:
    """Map one planned task to a stable execution/display category."""
    if task.task_type in {"food_delivery", "food_order"}:
        return "food_delivery"
    if task.task_type in {"restaurant_search", "restaurant_visit"}:
        return "restaurant"
    if task.task_type == "hotel_search":
        return "hotel_lounge"

    primary_text = " ".join(
        str(value or "").lower()
        for value in (task.target, task.search_query)
    ).strip()
    task_text = primary_text or str(task.description or "").lower()
    for category in (
        "hotel_lounge",
        "playground",
        "billiards",
        "tea_house",
        "tea_drink",
        "mountain_hiking",
        "fishing",
        "trampoline",
        "park",
        "cafe",
        "restaurant",
        "bar",
    ):
        if any(
            term.lower() in task_text
            for term in CATEGORY_RULES[category]["task_terms"]
        ):
            return category  # type: ignore[return-value]
    if task.task_type == "bar_visit":
        return "bar"
    return "unknown"


def category_label(category: str) -> str:
    """Return the user-facing label for a normalized task category."""
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS["unknown"])


def task_text_for_category(task: PlannedTask) -> str:
    return " ".join(
        str(value or "").lower()
        for value in (task.target, task.search_query, task.description)
    )
