# Design Document: Local Life Planning Agent

## 1. Problem & Goal

**用户不是想要推荐列表，而是想把本地生活安排这件事做完。**

传统推荐系统返回"你可能感兴趣的 POI/餐厅列表"，用户还需要手动查看详情、比较距离、检查空位、逐一预约下单——整个过程涉及 6-7 个独立操作，体验割裂。

本 Agent 的目标：**用户输入一句模糊需求 → Agent 自动规划完整路线 → 执行所有预约/下单动作 → 输出可转发消息。** 用户只需说一句话，其他全由 Agent 完成。

## 2. Agent Architecture (V2 — 13 阶段)

```
User Query (自然语言) + Location + Demo Scenario
       │
       ▼
┌──────────────────────────────────────┐
│           Frontend (React)           │
│  输入框 + 定位 + 流式开关 + 场景选择  │
│  → REST API (标准) 或 SSE (流式)     │
└──────────────┬───────────────────────┘
               │ POST /api/plan/v2 或 /api/plan/v2/stream
               ▼
┌──────────────────────────────────────┐
│       Backend API (FastAPI)          │
│  路由: plan_routes.py                │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│     Agent Orchestrator V2            │
│  orchestrator_v2.py / stream_orch.   │
│                                       │
│  1. Intent Parsing (DeepSeek/mock)    │
│  2. Location Resolution (GPS/manual/profile) │
│  3. Profile Merge (users.json + family/friends) │
│  4. POI + Restaurant Search (AMap/mock) │
│  5. Weather Query (AMap/mock)        │
│  6. Route Calculation (AMap/mock)    │
│  7. Ranking (6-dim weighted scoring) │
│  8. Feasibility Check (12 checks)    │
│  9. Plan Building (itinerary)        │
│ 10. Action Planning                  │
│ 11. Share Message Generation         │
│ 12. Execution (tool calls)           │
│ 13. Explanation (DeepSeek/mock)      │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌──────┐ ┌──────────┐
│ Tools  │ │Mock  │ │Providers │
│ Layer  │ │API   │ │(AMap/    │
│ 6个工具 │ │6个模块│ │DeepSeek) │
└────────┘ └──────┘ └──────────┘
```

## 3. Provider Abstraction

支持四种运行模式：

| Mode | LLM | POI | Route | Weather | Execution |
|------|:---:|:---:|:---:|:---:|:---:|
| `demo_real` | real→mock | real→mock | real→mock | real→mock | mock |
| `demo_safe` | mock | mock | mock | mock | mock |
| `development` | real→mock | real→mock | real→mock | real→mock | mock |
| `test` | mock | mock | mock | mock | mock |

Provider 选择逻辑在 `backend/config/settings.py` 中统一管理，通过 `APP_MODE` 环境变量切换。

## 4. Streaming Agent Trace (SSE)

流式接口 `POST /api/plan/v2/stream` 在 Agent 执行每个阶段时推送 SSE 事件：

事件类型：
- `trace` — 阶段进度（phase + status + message）
- `tool_call` — 工具调用结果（tool_name + success + message）
- `fallback` — fallback 触发（reason + action + result）
- `partial_itinerary` — 行程片段
- `final` — 完整最终响应
- `error` — 错误事件

前端使用 `fetch + ReadableStream` 解析 SSE，实时更新 Trace Panel 和 Tool Timeline。

## 5. Location Resolution

定位优先级：
1. Browser GPS (`navigator.geolocation`) — 前端获取
2. Manual address input — 通过 mock geocode 转换
3. User profile `home_location` — 从 `data/users.json`
4. System default — 城市中心点

`backend/agent/location_resolver.py` 统一处理，返回 `{lat, lng, address, source, confidence}`。

## 6. Fallback Demo Mode

通过 `demo_scenario` 参数可控制触发特定异常：

| Scenario | 触发机制 |
|------|------|
| `restaurant_full` | 执行后注入 fallback 记录 |
| `rainy_weather` | 覆盖 weather_data 为雨天 |
| `ticket_sold_out` | 切换到第二候选 POI |
| `optional_service_fail` | 过滤 extra_service 成功记录 |
| `route_too_far` | 切换到第二候选 POI |

所有 scenario 在 `orchestrator_v2._apply_demo_scenario_overrides()` 中处理。

## 7. V2 Planning Strategy (13 阶段)

| 阶段 | 模块 | 输入 | 输出 |
|------|------|------|------|
| 1. Intent Parsing | DeepSeek/mock LLM | 用户 query | scene, constraints |
| 2. Location Resolution | location_resolver | request location + user profile | origin_location |
| 3. Profile Merge | orchestrator_v2 | intent + users.json + profiles | 完整 constraints |
| 4. Candidate Retrieval | AMap/mock POI provider | constraints + keywords | POI + 餐厅候选 |
| 5. Weather | AMap/mock weather provider | city | weather_data |
| 6. Routes | AMap/mock route provider | origin + destinations | route_data |
| 7. Ranking | RankingEngine | candidates + routes + weather | ranked scores |
| 8. Feasibility Check | feasibility_v2 | top candidates + constraints | feasible + warnings |
| 9. Plan Building | plan_generator | ranked candidates | itinerary |
| 10. Action Planning | action_planner_v2 | selected plan | action list |
| 11. Share Message | share_message_v2 | plan + actions | WeChat message |
| 12. Execution | executor_v2 | actions + constraints | tool_calls + orders |
| 13. Explanation | ExplanationGenerator | plan + provider data | natural language |

## 8. Tool Calling Chain

家庭场景完整工具链:

```
search_poi → search_restaurant → get_weather → plan_route ×N
→ rank_candidates → check_feasibility → build_itinerary
→ create_ticket_order → create_restaurant_reservation
→ create_flower_or_cake_order → create_ride_order ×2
→ send_plan_message
```

## 9. Fallback Strategy

| 异常 | 处理方式 |
|------|----------|
| 餐厅无位 | 换时间 → 换同类型餐厅 |
| 活动无票 | 换时间 → 换 POI |
| 距离超限 | 直接过滤，planning_trace 记录 |
| 年龄不匹配 | 硬过滤，age_range 检查 |
| 工具调用失败 | retry 1次 → fallback 记录 + 手动建议 |
| 排队超 30min | 降权，优先低排队餐厅 |
| 天气不好 | 优先 indoor POI |
| optional 失败 | 跳过，不影响主流程 |

所有 fallback 记录在 `planning_trace` 和 `fallback_actions` 中。

## 10. Demo Scenario

**家庭场景:** 小明一家三口下午想去亲子活动 + 晚饭 → Agent 自动选择星河亲子探索乐园 + 轻氧家庭厨房，购票、预约、订蛋糕、打车、发消息一气呵成。

**朋友场景:** 4 人下午短时活动 + 晚饭 → Agent 选择适合社交拍照的地点，生成可转发到群的消息。

**流式展示:** 打开流式开关 → 实时看到 Agent 每一步进展。

**Fallback 展示:** 切换 demo_scenario → 可控触发餐厅无位/雨天/门票售罄等场景。

**定位展示:** 浏览器 GPS / 手动输入 / 默认地址三种方式。
