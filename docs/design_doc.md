# Design Document: Local Life Planning Agent

## 1. Problem & Goal

**用户不是想要推荐列表，而是想把本地生活安排这件事做完。**

传统推荐系统返回"你可能感兴趣的 POI/餐厅列表"，用户还需要手动查看详情、比较距离、检查空位、逐一预约下单——整个过程涉及 6-7 个独立操作，体验割裂。

本 Agent 的目标：**用户输入一句模糊需求 → Agent 自动规划完整路线 → 执行所有预约/下单动作 → 输出可转发消息。** 用户只需说一句话，其他全由 Agent 完成。

## 2. Agent Architecture

```
User Query (自然语言)
       │
       ▼
┌──────────────────────────────────────┐
│           Frontend (React)           │
│  输入框 → API 请求 → 结果展示        │
└──────────────┬───────────────────────┘
               │ POST /api/plan
               ▼
┌──────────────────────────────────────┐
│       Backend API (FastAPI)          │
│  路由: plan_routes.py                │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│     Agent Orchestrator               │
│  orchestrator.py — 主流程编排         │
│                                       │
│  1. parser.py      意图解析           │
│  2. scorer.py      候选评分           │
│  3. planner.py     行程构建           │
│  4. executor.py    动作执行           │
│  5. response_gen   响应生成           │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌──────┐ ┌──────────┐
│ Tools  │ │Mock  │ │Data      │
│ Layer  │ │API   │ │Loader    │
│ 11个工具│ │6个模块│ │JSON读取   │
└────────┘ └──────┘ └──────────┘
```

## 3. Planning Strategy (9 阶段)

| 阶段 | 模块 | 输入 | 输出 |
|------|------|------|------|
| 1. Intent Parsing | parser.py | 用户 query | scene: family/friends |
| 2. Constraint Extraction | parser.py | query + user profile | 结构化约束条件 |
| 3. Candidate Retrieval | poi/restaurant tools | constraints | POI + 餐厅候选列表 |
| 4. Feasibility Check | ticket/availability/travel tools | 候选列表 | 过滤 + 评分 |
| 5. Scoring | scorer.py | 候选 + 距离 + 可用性 | 排序后候选 |
| 6. Itinerary Construction | planner.py | top candidates | 时间线行程 |
| 7. Action Planning | executor.py | itinerary | action list |
| 8. Execution | executor.py + order tools | actions | 订单结果 |
| 9. Final Response | response_generator.py | 全部中间结果 | 完整响应 |

## 4. Tool Calling Chain

家庭场景完整工具链:

```
search_poi → search_restaurant → check_ticket_availability ×N
→ check_restaurant_availability ×N → check_queue_time ×N
→ estimate_travel_time ×N → create_ticket_order
→ create_restaurant_reservation → create_flower_or_cake_order
→ create_ride_order ×2 → send_plan_message
```

## 5. Fallback Strategy

| 异常 | 处理方式 |
|------|----------|
| 餐厅无位 | 换时间 → 换同类型餐厅 |
| 活动无票 | 换时间 → 换 POI |
| 距离超限 | 直接过滤，planning_trace 记录 |
| 年龄不匹配 | 硬过滤，age_range 检查 |
| 工具调用失败 | retry 1次 → fallback 记录 + 手动建议 |
| 排队超 30min | 降权，优先低排队餐厅 |

所有 fallback 记录在 `planning_trace` 和 `fallback_actions` 中，便于评委查看。

## 6. Demo Scenario

**家庭场景:** 小明一家三口下午想去亲子活动 + 晚饭 → Agent 自动选择星河亲子探索乐园 + 轻氧家庭厨房，购票、预约、订蛋糕、打车、发消息一气呵成。

**朋友场景:** 4 人下午短时活动 + 晚饭 → Agent 选择美罗城 + 绿意素食坊，兼顾社交、拍照、聊天需求。
