# Sample Inputs & Outputs

## 家庭场景

### Input

```json
{
  "user_id": "u_001",
  "query": "今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。"
}
```

### Output

```json
{
  "status": "success",
  "scene": "family",
  "summary": "推荐方案：亲子轻松下午路线\n\n下午从家出发，前往星河亲子探索乐园游玩，随后前往轻氧家庭厨房享用晚餐，预计18:16左右到家。已为您自动完成门票购买、餐厅预约和打车订单。",
  "constraints": {
    "scene": "family",
    "start_time": "14:00",
    "end_time": "19:00",
    "duration_min": [240, 360],
    "max_distance_km": 8,
    "child_age": 5,
    "party_size": 3,
    "preferences": ["child_friendly", "low_fat", "not_too_far", "indoor_preferred"],
    "must_include": ["activity", "meal"],
    "optional_extra": ["cake", "flower"],
    "transport": "taxi"
  },
  "itinerary": [
    {"time_start": "14:00", "time_end": "14:18", "type": "travel", "title": "打车前往星河亲子探索乐园"},
    {"time_start": "14:18", "time_end": "15:58", "type": "activity", "title": "星河亲子探索乐园"},
    {"time_start": "15:58", "time_end": "16:08", "type": "travel", "title": "前往轻氧家庭厨房"},
    {"time_start": "16:30", "time_end": "17:40", "type": "meal", "title": "晚餐@轻氧家庭厨房"},
    {"time_start": "17:40", "time_end": "18:00", "type": "extra", "title": "顺路取低糖蛋糕"},
    {"time_start": "18:00", "time_end": "18:16", "type": "return", "title": "打车回家"}
  ],
  "completed_actions": [
    {"type": "ticket_order", "result": {"order_id": "TKT_XXXXXXXX"}},
    {"type": "restaurant_reservation", "result": {"reservation_id": "RESV_XXXXXXXX"}},
    {"type": "extra_service_order", "result": {"order_id": "CAKE_XXXXXXXX"}},
    {"type": "ride_order", "result": {"ride_id": "RIDE_XXXXXXXX"}},
    {"type": "send_message", "result": {"message_id": "MSG_XXXXXXXX"}}
  ],
  "share_message": "搞定了，下午 14 点出发，先去星河亲子探索乐园，孩子能玩一个多小时；下午5点左右去轻氧家庭厨房吃饭，我已经约好了 3 人位，有低脂套餐和儿童餐；饭后顺路取低糖蛋糕，预计 18 点多到家。"
}
```

---

## 朋友场景

### Input

```json
{
  "user_id": "u_001",
  "query": "今天下午我们 4 个人，2 男 2 女，想出去玩几个小时，顺便吃饭，别太远。"
}
```

### Output

```json
{
  "status": "success",
  "scene": "friends",
  "summary": "推荐方案：轻社交朋友下午路线\n\n下午出发，前往美罗城商场主题展，随后前往绿意素食坊享用晚餐。已为您自动完成门票购买、餐厅预约和打车订单。",
  "constraints": {
    "scene": "friends",
    "start_time": "14:00",
    "end_time": "19:00",
    "max_distance_km": 10,
    "party_size": 4,
    "preferences": ["social", "photo_friendly", "good_food", "not_too_tiring", "chat_friendly"]
  },
  "share_message": "搞定了，下午 14:00 出发，先去美罗城商场主题展，大概玩到4点多；然后去附近逛一下，下午6点去绿意素食坊吃饭，我已经约了 4 人位。全程打车20分钟左右，适合拍照聊天，不会太累。"
}
```
