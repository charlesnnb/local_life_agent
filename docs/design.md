# Local Life Agent 设计说明

Local Life Agent 的目标不是返回一个 POI 列表，而是把一句自然语言生活需求拆成有顺序的任务，逐项调用工具，并生成可确认、可执行、可异常重规划的完整行程。系统输出包含 Ordered Tasks、候选选择依据、Route、Timeline、Mock Action 状态、Replan Proposal、Share Message 和可展开的 Agent Trace。

## 1. Planning 策略与主流程

API 入口是 `POST /api/plan` 与 `POST /api/plan/stream`，二者最终都进入 `PlannerAgent.run(...)`；SSE 只负责展示进度，不是第二套规划器。重规划确认入口是 `POST /api/replan/confirm`，只在用户选择方案后调用 `apply_replan(...)` 更新计划副本。

```text
自然语言输入
  ↓
Intent Parsing
提取时间、同行人、child_age、距离、饮食、预算、避免条件
  ↓
Task Planning
拆分 Ordered Tasks，保留任务顺序、time_window、route_needed
  ↓
Tool Routing
逐项路由到 POI / Restaurant / Food Order 工具
  ↓
Candidate Selection
相关性验证 → 任务感知排序 → 用户偏好微调
  ↓
Itinerary Composition
生成结构化 Route、Timeline、Actions、Plan Steps
  ↓
Exception Detection
检测餐厅无座、活动不可用、交通/时间冲突
  ↓
Consent & Replan
展示替代方案；用户确认后再更新计划
```

| 策略 | 当前代码实现 | 解决的问题 |
| --- | --- | --- |
| 结构化意图解析 | `llm_intent_parser` 优先请求 LLM JSON；失败回到 `intent_parser` 规则解析。规则解析提取 `scene`、`time_window`、`duration_hours`、同行人、`child_age`、人数、距离、饮食、预算、天气和避免条件。 | 把口语化需求转成可校验、可排序的约束。 |
| Ordered Task Planning | `llm_task_planner` 只让 LLM 拆分和排序任务，不允许编造地点；返回值经 Pydantic 校验、`task_id` 归一和工具字段归一。失败时 `task_decomposer` 按原句分句规则 fallback。 | 避免多阶段需求被压成“一个活动 + 一个餐厅”。 |
| Task-level Context | `apply_task_context` 按任务所属分句挂载 companions、`child_age`、constraints；酒吧等成人任务不会自动继承家庭/儿童约束，显式带孩子才提示风险。 | 防止全局 child_age 或家庭场景污染无关任务。 |
| Task-aware Selection | `validate_candidate` 先按任务类别命中正向词/排除词过滤候选；`rank_task_candidates` 再综合相关性、距离、评分、等待、偏好、时段、预算、室内外、儿童适配排序。 | 不直接采用 AMap 第一条结果，避免弱相关地点进入行程。 |
| Structured Itinerary | `compose_itinerary` 只用 `ToolExecutionResult` 组装 `RoutePlan`、`Timeline`、`ActivityPlan` 和 `ActionResult`；外卖进 Timeline/Actions，但 `route_needed=false`，不进入线下 Route。 | 保证地点顺序、到达时间、动作和分享消息来自同一份结构化事实。 |

## 2. 工具调用链路与 Provider 边界

- **Agent / Planning Layer**：`PlannerAgent`、`llm_intent_parser`、`llm_task_planner`、`ToolRouter`、`compose_itinerary`、`final_composer` 负责编排主流程、维护任务顺序、生成结构化计划和校验最终文案。
- **Tool Layer**：`poi_tool`、`restaurant_tool`、`food_order_tool`、`route_tool`、`reservation_tool`、`message_tool` 负责搜索候选、模拟点餐/预约/消息、路线估算，并统一输出 `ToolExecutionResult` 或 `ActionResult`。
- **Provider Layer**：`DeepSeekProvider`、`AmapProvider`、`local_commerce_provider` 和本地 JSON 数据构成外部 API / fallback 边界；LLM 与 AMap 可失败，本地数据与 Mock Commerce 提供 deterministic fallback 和交易字段补充。

`ToolRouter.execute(...)` 对每个 `PlannedTask` 独立执行：`food_delivery` 调 `order_food`，`restaurant_search` 调 `search_restaurants`，`poi_search`/`bar_visit`/`hotel_search` 调 `search_task_pois`。AMap 只提供 geocode、place search、route duration；等待时间、价格、儿童友好、饮食适配、预约能力等由本地 commerce enrichment 或 JSON mock 补齐。Planning 层依赖统一结构，不依赖某个具体 Provider 的原始响应。

`final_composer` 可以调用 LLM 优化摘要和分享文案，但它不能修改地点、时间、路线和执行结果；代码会校验必需地点、必需时间、允许时间集合、支付/预约状态，并在冲突时回退到结构化行程派生的 deterministic 文案。

关键代码依据：`src/app.py` 定义 API 入口；`PlannerAgent.run` 是唯一主编排；`ToolRouter` 完成 task-to-tool；`result_validator` 与 `task_ranker` 保证候选先相关再排序；`compose_itinerary` 与 `final_composer` 保证 Route、Timeline、Actions、Summary 和 Share Message 的一致性。

## 3. 异常处理闭环

异常检测由 `detect_exceptions(...)` 完成，只产出 `PlanException`，不修改当前计划。`build_replan_proposals(...)` 生成可展示选项，前端 `ExceptionConfirmationCard` 要求用户选择“接受方案”或“保持原计划”；只有 `POST /api/replan/confirm` 才会对计划副本应用变更。

| 异常 | 检测条件 | Replan 方案 |
| --- | --- | --- |
| `restaurant_full` | Mock 预约失败、动作详情包含 `restaurant_full`，或 Demo/Hybrid 指定餐厅满员场景。 | 更换低等待餐厅并更新路线、时间线、模拟预约、分享消息；或保留原餐厅。 |
| `activity_unavailable` | Demo 场景模拟活动售罄、场馆关闭或 unavailable；基于原任务和候选结果定位同类替代。 | 更换同类且满足原约束的活动；若没有合格备选，明确提示放宽距离或更换活动类型，不硬选无关地点。 |
| `schedule_conflict` | 交通延误后预计到达晚于预约时间，影响后续安排。 | 调整模拟预约时间、切换低等待餐厅，或保持原计划并显示风险。 |

统一闭环是：`Detect → Assess Impact → Generate Options → User Consent → Apply Replan`。接受替代地点时，`replan_service` 更新 `RouteStop`、相关 Timeline/Plan Step 文案、模拟预约状态、Share Message 和 `natural_language`；选择保留时仅记录风险，不覆盖原计划。

## 4. Fallback、运行模式与 Mock 边界

| 模式 | 查询与规划 | 执行动作 | 用途 |
| --- | --- | --- | --- |
| Demo | 强制 Rule/Mock LLM、本地 POI/餐厅/路线数据 | Mock | 零 Key、离线评审、稳定异常场景。 |
| Hybrid | 使用配置的真实 LLM Provider（当前代码类为 `DeepSeekProvider`，OpenAI-style 接口）与 AMap；失败自动 fallback | Mock | 比赛视频与主要展示。 |
| Live | 打开真实 LLM/AMap 查询 Provider | 未实现真实交易时标记为 `mock_fallback` | 未来扩展真实 Action Provider。 |

LLM 失败会回到规则 Intent/Task Planner；AMap 失败、超时、限流、空结果或无效响应会回到本地候选和离线路线估算。当前点餐、预约、消息发送都是 Mock Action，不代表真实下单、真实支付、真实订座或真实消息发送；项目没有实现真实购票、打车、支付、微信发送、实时库存或天气动态推送。

## 5. 输出与评委可读性

最终响应结构是：

```text
Plan Summary
+ Ordered Tasks
+ Route
+ Timeline
+ Replan Proposal
+ Mock Action Status
+ Share Message
+ Explainable Agent Trace
```

普通用户优先看到最终方案、时间线、地图、Mock Action 状态和分享消息；Agent 执行过程、候选过滤原因、Provider source 和 fallback 细节默认折叠，评委可展开查看任务拆解、工具调用和候选筛选证据。

## 6. 技术亮点

1. **Task-first Planning**：先拆解并执行有序任务，而不是直接返回推荐列表。
2. **Task-aware Tool Chain**：任务相关性优先，偏好、距离、等待和预算作为二级排序。
3. **Consent-based Recovery**：异常不会直接破坏计划，用户确认后才重规划。
