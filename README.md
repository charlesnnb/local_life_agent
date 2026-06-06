# Local Life Agent MVP

一句话生成一个可直接执行的本地短时活动方案，并模拟完成餐厅预约和计划消息发送。

## 本次重构总结

这个项目最初同时存在 V1/V2、多个 orchestrator、复杂 trace、订单/门票/打车等尚未服务于 Demo 主目标的功能。此次重构没有继续兼容旧结构，而是围绕一个清晰问题重新收敛：

> 用户说一句自然语言后，Agent 不只推荐地点，而是把活动、餐厅、路线、时间线和后续动作组合成一个可以直接执行的本地生活方案。

本次对话中完成了以下阶段：

### 1. MVP 架构重构

- 删除 V1/V2 和重复 orchestrator，统一为 `PlannerAgent.run(...)` 单一主流程。
- 保留简洁的 FastAPI 外壳和 JSON 数据读取逻辑。
- 将意图解析、排序、计划构建、工具调用、执行动作和 schema 拆到独立模块。
- 保留 `POST /api/plan`，并新增 CLI。
- 使用本地 JSON 数据跑通活动、餐厅、路线、预约和消息发送流程。

### 2. 强意图解析

- 支持家庭、朋友、情侣和个人场景。
- 支持时间窗口、活动时长、同行人、人数、孩子年龄和男女组合。
- 支持距离、预算、活动类型、减脂/清淡饮食、天气和避雷约束。
- 规则解析始终保留，外部 LLM 不可用时仍能生成完整方案。

### 3. 路线和可执行时间线

- 增加结构化 `route` 和 `timeline`。
- 默认位置固定为“上海徐汇”，不再把完整家庭地址错误识别成城市。
- 所有 Mock 通勤时间限制在合理范围，避免出现 1778 分钟等异常结果。
- 前端增加路线概览和纵向时间线组件。
- 路线结构预留 `polyline`，可继续接入高德地图 JS API。

### 4. 流式 Agent 执行过程

- 在同一个 `PlannerAgent.run(query, event_callback=...)` 中增加进度事件。
- `POST /api/plan` 和 `POST /api/plan/stream` 共用同一条规划逻辑。
- SSE 实时展示意图解析、活动搜索、餐厅搜索、路线规划、时间线、预约和消息生成过程。
- callback 失败不会中断主流程。

### 5. 用户偏好与个性化排序

- 增加轻量偏好问卷和内存 profile。
- 支持活动类型、通勤上限、餐饮偏好、活动强度、预算、室内优先和少排队。
- 将问卷转换为归一化 ranking weights。
- POI 和餐厅排序同时考虑距离、活动匹配、儿童友好、饮食、评分、预算、室内和等待时间。
- 返回 `preference_explanation`，让用户知道偏好如何影响推荐。

### 6. Task-first 框架纠偏

- 新增 `llm_task_planner`，由 DeepSeek 优先把自然语言拆成结构化、带顺序的 `PlannedTask`。
- LLM 只判断任务、工具和路线需求，不生成 POI，不编造执行结果。
- DeepSeek 不可用或 JSON/schema 校验失败时，规则 fallback 生成同一任务契约。
- 新增 `tool_router`，逐项调用外卖、POI、餐厅、酒吧和酒店搜索能力。
- 新增 `itinerary_composer`，只消费 ordered tasks 与 `ToolExecutionResult`，统一生成路线、时间线、动作、消息和冲突提示。
- `food_delivery` 进入 timeline/actions，但不会加入线下 route。
- 多个下午活动不会静默消失；体力或时间偏紧时返回 `planning_warnings` 和备选建议。
- 普通家庭 Demo 同样走 task-first 主链路，旧固定流程只作为最终兼容 fallback。
- 整个系统仍只有 `PlannerAgent.run(...)` 一个编排入口，没有新增 V3 或 streaming orchestrator。

多阶段流程：

```text
自然语言
→ llm_task_planner（失败时规则 fallback）
→ structured ordered tasks
→ tool_router / tool executor
→ AMap / food / restaurant / hotel / bar tools
→ itinerary_composer
→ route + timeline + actions + message
```

### 7. DeepSeek 与高德真实 API

- DeepSeek 接入任务规划，并保留意图解析、搜索词规划、决策解释和最终文案能力供兼容流程使用。
- 所有 LLM JSON 输出经过 `json.loads` 和 Pydantic 校验。
- 不展示 hidden chain-of-thought，只返回可公开展示的 `public_reasoning`。
- 高德接入地理编码、活动 POI、餐厅搜索和最终三段路线。
- 候选排序使用本地坐标估算，仅为最终选中的路线调用高德，避免触发路线接口 QPS 限制。
- 高德返回的地点、坐标和路线是真实数据；评分、价格、排队、儿童友好、减脂友好和预约能力由 Mock Local Commerce 补充。
- 外部 API 缺少 key、超时、HTTP 异常、非法 JSON、schema 不匹配或异常路线时自动回退。

### 8. 前端与质量保障

- 前端展示偏好设置、流式 Agent 进度、路线、时间线、推荐解释和可发送消息。
- 明确标记事件来源：`DeepSeek`、`AMap`、`Mock fallback`。
- 明确标记地点和路线来源：`amap` 或 `mock`。
- 新增意图、路线、时间线、streaming、偏好、DeepSeek fallback 和 AMap fallback 测试。
- 当前验证结果：`61 passed`，前端 `npm run build` 通过。

## 核心设计思想

### Agent 的目标是完成任务

系统的输出不是“这里有几个推荐”，而是：

```text
理解需求
→ 拆成有序任务
→ 按任务选择并执行工具
→ 合并工具结果
→ 规划路线、时间和冲突提示
→ 模拟点餐、预约与消息
→ 生成可直接转发的消息
```

推荐只是中间步骤，可执行计划才是最终产品。

### 主流程只能有一套

普通接口、流式接口、Mock 模式和真实 API 模式都复用：

```python
PlannerAgent.run(query, event_callback=None)
```

流式输出只是观察同一主流程的进度，不复制规划逻辑，也不新增 streaming orchestrator。

### LLM 负责理解和表达，代码负责事实和约束

- LLM 适合拆分任务、判断工具、解析自然语言、解释选择和润色文案。
- Pydantic schema、排序函数、路线边界和计划构建器负责确定性约束。
- LLM 不直接决定不存在的地点，不得修改已选地点、时间线或执行结果。
- LLM 输出异常时立即使用规则结果，不让自由文本污染核心流程。

### Provider、Tool 和 Planner 分层

- `providers/`：处理 DeepSeek、高德等外部协议、认证、超时和响应解析。
- `tools/`：提供统一的活动、餐厅、路线、预约和消息能力。
- `core/`：负责意图、搜索词、排序、计划、解释和最终文案。
- `PlannerAgent`：只编排步骤，不承载所有业务细节。

真实供应商变化时，应替换 provider 或 tool，而不是重写 Agent。

### Mock 是可靠降级，不是临时代码

Mock 数据保证比赛 Demo 在无网络、无 key、限流或第三方异常时仍能完整运行。每个外部能力都应满足：

```text
真实 API 成功 → 使用真实结果
真实 API 失败 → 发出 fallback 事件 → 使用 Mock/规则结果
```

无论外部状态如何，`/api/plan` 和 `/api/plan/stream` 都应尽量返回完整方案。

### 数据来源必须透明

- `source=amap`：地点身份或路线来自高德。
- `source=mock`：使用本地数据或 Mock fallback。
- 商户评分、排队和预约目前不是高德或美团真实交易数据，必须明确标记为 Mock Local Commerce。
- 不把“模拟预约成功”描述成真实下单或真实支付。

### 安全和可解释性优先

- API key 只从 `.env` 或环境变量读取。
- `.env` 不提交到 Git，`.env.example` 只保留变量名。
- 流式事件只展示公开阶段和 `public_reasoning`。
- 决策解释只能引用候选地点。
- 最终文案不能修改既定地点、时间或预约状态。

## 当前主流程

```text
自然语言
→ 当前用户偏好与归一化权重
→ DeepSeek LLM Task Planner（失败时规则 task planner）
→ PlannedTask[]
→ Tool Router
→ 高德 POI / 餐厅 / 酒吧 / 酒店或 Mock food order
→ ToolExecutionResult[]
→ Itinerary Composer
→ route + timeline + actions + planning_warnings
→ Mock 预约与消息发送
→ JSON + 自然语言方案
```

`POST /api/plan` 和流式接口最终返回的响应包含：

- `user_intent`：结构化意图、`tasks`、`time_windows` 与约束
- `task_plan`：LLM 或 fallback 生成的有序任务、工具选择与路线需求
- `plan`：活动方案与推荐理由
- `route`：仅包含 `route_needed=true` 的线下地点和通勤
- `timeline`：前端可直接渲染的可执行时间线
- `actions`：当前 MVP 的 Mock 执行结果
- `planning_warnings`：任务冲突、时间偏紧和备选建议
- `preference_explanation`：偏好如何影响本次推荐
- `decision_explanation`：只基于候选地点生成的公开选择依据
- `composition`：最终摘要、路线说明和可转发消息

每个地点和路线都带有 `source`。值为 `amap` 时表示地点身份或路线来自高德，值为 `mock` 时表示使用本地数据；`route.polyline` 会在高德返回时保留，供后续地图组件使用。

## 项目结构

```text
src/
  main.py
  app.py
  config/settings.py
  schemas/models.py
  agents/
    planner_agent.py
    executor_agent.py
  core/
    intent_parser.py
    task_decomposer.py
    llm_task_planner.py
    tool_router.py
    itinerary_composer.py
    itinerary_builder.py
    llm_intent_parser.py
    query_planner.py
    decision_explainer.py
    final_composer.py
    plan_builder.py
    ranking.py
  providers/
    deepseek_provider.py
    amap_provider.py
    local_commerce_provider.py
  tools/
    poi_tool.py
    food_order_tool.py
    restaurant_tool.py
    weather_tool.py
    route_tool.py
    reservation_tool.py
    message_tool.py
  services/location_service.py
  services/preference_service.py

data/
  pois.json
  restaurants.json
  availability.json
  travel_times.json
  weather.json

tests/test_demo_flow.py
tests/test_preferences.py
tests/test_deepseek_fallback.py
tests/test_amap_fallback.py
tests/test_llm_task_planner.py
tests/test_tool_router.py
tests/test_task_driven_planning.py
```

## 安装

```bash
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

## 外部 API 配置

项目默认关闭外部 API，可直接使用原有规则和 Mock 数据。复制 `.env.example` 中的变量名到本地 `.env`，按需配置：

```bash
ENABLE_LLM=true
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=20

ENABLE_AMAP=true
AMAP_API_KEY=
AMAP_BASE_URL=https://restapi.amap.com
AMAP_TIMEOUT_SECONDS=10
```

- 开关为 `false` 时不会调用对应外部 API。
- 开关为 `true` 但 key 缺失、超时、HTTP 异常、JSON 非法或 schema 校验失败时自动回退。
- `.env` 已被 `.gitignore` 忽略，不应提交真实 key。
- 若真实 key 曾经进入 Git 历史，应立即在对应平台重新生成。

DeepSeek 使用 OpenAI-compatible Chat Completions API。主链路使用它生成严格 JSON 的 ordered task plan；兼容流程仍保留意图解析、搜索词规划、决策解释和最终文案能力。所有结构化输出均经过 `json.loads` 和 Pydantic 校验，不向前端暴露 hidden chain-of-thought。

高德 Web Service API 用于地理编码、POI/餐厅搜索和路线估算。当前 Demo 中，地图 POI 和路线可使用高德真实 API；餐厅评分、排队、预约等本地生活交易数据使用 Mock Local Commerce Provider 模拟，后续可以替换为真实商户平台或 MCP 工具。

## CLI

```bash
python src/main.py "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"
```

仅输出 JSON：

```bash
python src/main.py --json-only "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"
```

## FastAPI

```bash
python run_backend.py
```

打开 <http://localhost:8000>，或调用：

`HOST=0.0.0.0` 表示服务监听所有本机网络接口，但 `0.0.0.0` 不是浏览器访问地址。浏览器应使用：

```text
http://localhost:8000
```

或：

```text
http://127.0.0.1:8000
```

```bash
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"query":"今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"}'
```

流式查看 Agent 执行过程：

```bash
curl -N -X POST http://localhost:8000/api/plan/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"}'
```

- `POST /api/plan`：普通 JSON 响应
- `POST /api/plan/stream`：SSE progress 事件，最后发送完整 result

启用 DeepSeek 后，可在 SSE 中看到 `source: "deepseek"` 的 `llm_intent_finished`、`query_planning_finished`、`decision_explanation_finished` 和 `final_composer_finished`。若调用失败，会出现 `api_fallback_triggered`，最终仍返回完整方案。

Task-first 主链路还会发送
`llm_task_planning_started`、`llm_task_planning_finished`、
`tool_routing`、`tool_execution` 和 `itinerary_composing`。

启用高德后，可检查：

```bash
curl -s -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"query":"今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁"}'
```

返回中的 `plan.steps[].source`、`route.stops[].source` 或 `route.source` 为 `amap`，说明真实高德数据已生效；为 `mock` 则表示已回退。

偏好接口：

```bash
curl http://localhost:8000/api/preferences/default

curl -X POST http://localhost:8000/api/preferences \
  -H 'Content-Type: application/json' \
  -d '{
    "activity_types": ["亲子乐园", "展览"],
    "max_travel_minutes": 30,
    "dining_preferences": ["清淡健康", "亲子友好"],
    "activity_intensity": "light",
    "budget_level": "medium",
    "prefer_indoor": true,
    "prefer_low_wait": true
  }'

curl http://localhost:8000/api/preferences/current
```

偏好当前保存在服务进程内存中，重启后恢复默认 profile。

如 8000 端口被占用：

```bash
PORT=8010 python run_backend.py
```

## 测试

```bash
python -m pytest

python -m pytest tests/test_llm_task_planner.py
python -m pytest tests/test_tool_router.py
python -m pytest tests/test_task_driven_planning.py
```

## 后续接入

- 地图可视化：读取 `route.origin`、`route.stops` 和 `route.polyline` 接入高德 JS API。
- 更多高德能力：扩展 `src/providers/amap_provider.py`，保持 tools 的内部 schema 不变。
- 真实商户数据：替换 `src/providers/local_commerce_provider.py`。
- 真实预约或下单：替换 `src/tools/reservation_tool.py` 或 `food_order_tool.py`
- 微信、短信或其他消息渠道：替换 `src/tools/message_tool.py`
- MCP 预约工具：在 `ExecutorAgent` 中注入实现相同结构化输入输出的 reservation tool，并保留当前 Mock fallback。

Agent、排序和时间表无需因工具实现变化而重写。
