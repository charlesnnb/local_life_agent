"""Priority 1 coverage for structured intent and constraint parsing."""

from src.core.intent_parser import parse_intent
from src.core.task_decomposer import decompose_planned_tasks


def test_family_child_and_diet_constraints():
    query = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"

    intent = parse_intent(query)

    assert intent.raw_query == query
    assert intent.scene == "family"
    assert intent.time_window == "今天下午"
    assert intent.duration_hours == [3.0, 4.0]
    assert intent.companions == ["老婆", "孩子"]
    assert intent.party_size == 3
    assert intent.child_age == 5
    assert intent.distance_preference == "nearby"
    assert {"亲子", "轻松"} <= set(intent.activity_preferences)
    assert {"减脂", "清淡", "低油"} <= set(intent.diet_preferences)
    assert "太远" in intent.avoid


def test_friends_gender_activity_and_budget_constraints():
    query = "今天下午和4个朋友出去玩，2男2女，想找个能聊天、拍照、吃饭方便的地方，别太贵"

    intent = parse_intent(query)

    assert intent.scene == "friends"
    assert intent.time_window == "今天下午"
    assert intent.party_size == 4
    assert intent.gender_mix == {"male": 2, "female": 2}
    assert intent.companions == ["朋友"]
    assert {"聊天", "拍照", "吃饭"} <= set(intent.activity_preferences)
    assert intent.budget_preference == "not_expensive"


def test_couple_quiet_dinner_walk_constraints():
    query = "晚上想和老婆找个安静点的地方吃饭散步，不想太吵"

    intent = parse_intent(query)

    assert intent.scene == "couple"
    assert intent.time_window == "晚上"
    assert intent.companions == ["老婆"]
    assert intent.party_size == 2
    assert {"安静", "吃饭", "散步"} <= set(intent.activity_preferences)
    assert "太吵" in intent.avoid


def test_weekend_rain_indoor_constraints():
    query = "周末可能下雨，想找个室内能逛逛吃饭的地方"

    intent = parse_intent(query)

    assert intent.time_window == "周末"
    assert intent.weather_constraint == "rain"
    assert {"室内", "逛逛", "吃饭"} <= set(intent.activity_preferences)
    assert "户外" in intent.avoid


def test_citywalk_with_cuisine_creates_activity_and_restaurant_tasks():
    intent = parse_intent(
        "今天下午想和朋友去 citywalk 然后吃川菜，"
        "预算别太高，不想排队太久"
    )

    assert intent.scene == "friends"
    assert intent.budget_preference == "not_expensive"
    assert "排队" in intent.avoid
    assert "citywalk" in intent.activity_preferences
    assert "川菜" in intent.diet_preferences

    tasks = decompose_planned_tasks(intent.raw_query, intent)
    assert [task.task_type for task in tasks] == [
        "poi_search",
        "restaurant_search",
    ]
    assert "citywalk" in tasks[0].target.lower()
    assert "川菜" in tasks[1].search_query
