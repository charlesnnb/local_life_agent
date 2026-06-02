# Local Life Agent

一句话安排你的本地休闲活动 — 输入"下午带孩子出去玩，顺便吃个饭"，Agent 自动帮你规划完整方案。

## 快速开始（5 分钟）

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

然后编辑 `.env` 文件，填入你的 API Key：

```env
# 运行模式（推荐 demo_safe 先试试）
APP_MODE=demo_safe

# DeepSeek API Key — 用于理解你的自然语言需求
# 免费注册获取：https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-你的key

# 高德地图 API Key — 用于搜索地点、路线、天气
# 免费注册获取：https://console.amap.com/dev/key/app
AMAP_API_KEY=你的key
```

> **没有 API Key 也能跑：** 使用 `APP_MODE=demo_safe` 或 `development`，系统会用模拟数据运行。

### 3. 启动

```bash
python run_backend.py
```

浏览器打开 **http://localhost:8000**，输入需求，点"开始规划"。

---

## 运行模式

| 模式 | 用途 | LLM/POI/天气/路线 | 执行动作 | 需要 API Key |
|------|------|:---:|:---:|:---:|
| `demo_real` | 比赛展示 / 录制视频 | 真实 API 优先，mock 兜底 | mock | 推荐填 |
| `demo_safe` | 现场兜底 / 稳定展示 | 全部 mock | mock | 否 |
| `development` | 本地开发 | 有 key 用真实，无 key 用 mock | mock | 否 |
| `test` | 自动化测试 | 全部 mock | mock | 否 |

### demo_real vs demo_safe

**demo_real** — 适合录制演示视频、网络稳定时现场展示：
- 使用真实 DeepSeek + 高德地图 API
- 展示真实地点、真实路线、真实天气
- 如果真实 API 失败，自动 fallback 到 mock
- 票务、预约、打车、消息仍使用 mock（不涉及真实支付/隐私）

**demo_safe** — 适合比赛现场兜底、网络不稳定时：
- 全部使用 mock 数据，结果稳定可控
- 不依赖任何外部网络
- 不会因为 API 限流/超时翻车
- 配合 Demo Scenario 可以稳定触发各种 fallback 场景

```bash
# 切换模式只需改 .env
APP_MODE=demo_real   # 真实 API 展示
APP_MODE=demo_safe   # 稳定 mock 展示
```

### 前端模式切换

页面顶部有模式切换开关，点击即可在 `demo_real` 和 `demo_safe` 之间切换，**无需重启后端**。切换后右侧 Provider 状态指示灯会实时更新。

---

## Agent Pipeline（13 阶段）

当前主流程是 Local Life Agent Pipeline，完整执行链路：

意图解析 → 定位解析 → 用户画像融合 → POI/餐厅搜索 → 天气查询 → 路线计算 → 候选排序 → 构建方案 → 可行性检查 → 动作计划 → 分享消息 → 工具执行 → 方案解释

### 位置识别

定位优先级：**浏览器 GPS > 手动输入 > 用户输入识别 > 用户默认地址 > 系统默认**

支持 50+ 中国城市的地理编码数据库（包括 湖州、沧州 等全部省会及主要城市）。当用户在 query 中明确提到城市名（如"我在湖州市"），该城市一定会被使用，**绝不会错误 fallback 到上海**。即使高德地理编码失败，也会使用内置的城市中心坐标 fallback。

### POI 搜索 & 距离过滤

搜索采用三级 fallback 链：
1. **关键词搜索** — 根据 scene 和 query 生成关键词，调用 AMap POI 搜索
2. **扩大搜索** — 如果无结果，用通用关键词（景点/公园/博物馆/商场）重新搜索
3. **Mock fallback** — 如果仍然无结果，使用内置的城市专属 POI 数据（含 湖州/沧州 等城市的景点、博物馆、酒吧等）

**距离过滤：** AMap 的城市过滤不严格，有时会返回其他城市的 POI。系统在每次 AMap 搜索后自动用 haversine 公式过滤掉距离出发地超过 **80km** 的候选。

### Scene 智能推断

当 LLM 没有返回明确场景时，系统通过关键词启发式推断：
- `老婆/孩子/宝宝/家人` → family
- `朋友/聚会/哥们/闺蜜` → friends
- `女朋友/男朋友/约会` → couple
- `旅游/景点/酒吧/一个人` → solo（默认也使用 solo，而非 family）

这避免了"在湖州市，推荐旅游景点"被错误识别为家庭出游。

### API 调用保护

- 所有外部 API 调用都有 **15 秒超时**保护（`asyncio.wait_for`）
- AMap API 调用之间间隔 **0.5 秒**，避免触发免费版 QPS 限制
- 路线计算最多请求 **5 条**（免费版 driving direction QPS 仅 1-2）
- 任何 API 失败都不中断流程，自动进入下一级 fallback

---

## 流式输出 (SSE)

前端默认使用流式输出，实时看到 Agent 每一步执行过程。如果流式连接失败，自动 fallback 到普通请求。

```bash
# 主流式接口
curl -X POST http://localhost:8000/api/plan/stream \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"下午带孩子出去玩"}'
```

前端会实时显示：
- Agent Planning Trace 逐步追加
- Tool Call Timeline 实时更新
- Fallback 事件即时展示
- Partial Itinerary 实时推送
- Final 事件到达后填充完整结果

事件类型：`trace` / `tool_call` / `fallback` / `partial_itinerary` / `final` / `error`

---

## Demo Scenario（可控异常展示）

比赛 Demo 时可以稳定触发各种 fallback 场景。

前端下拉框选择，或 API 传 `demo_scenario` 参数：

| Scenario | 效果 |
|------|------|
| `normal` | 正常模式 |
| `restaurant_full` | 强制触发餐厅无位 fallback（17:00 切换） |
| `rainy_weather` | 强制天气为雨天，优先室内活动 |
| `ticket_sold_out` | 强制门票售罄，切换到第二候选 POI |
| `optional_service_fail` | 强制蛋糕/咖啡下单失败，主流程不受影响 |
| `route_too_far` | 强制第一候选距离过远，切换到更近候选 |

```bash
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"下午带孩子出去玩","demo_scenario":"restaurant_full"}'
```

---

## 为什么执行动作仍使用 Mock API

票务购买、餐厅预约、打车、微信消息这些操作涉及：
- 真实平台权限（美团/滴滴/微信不开放此类 API）
- 支付和资金安全
- 用户隐私（手机号、家庭地址）

因此在任何模式下，执行动作（ticket/restaurant/ride/message）始终使用 mock API。这意味着：
- 不会产生真实订单
- 不会扣费
- 不会发送真实微信消息

Demo 中展示的是完整的 Agent 规划和执行能力，而非真实的支付系统。

---

## 怎么获取 API Key？

**DeepSeek（5 分钟）：**
1. 打开 https://platform.deepseek.com
2. 注册账号 → 点击「API Keys」→ 「创建 API Key」
3. 复制 key，填入 `.env` 的 `DEEPSEEK_API_KEY`
4. 新用户送免费额度，够测试用

**高德地图（3 分钟）：**
1. 打开 https://console.amap.com/dev/key/app
2. 注册/登录 → 「创建新应用」→ 「添加 Key」
3. 服务平台选「Web服务」→ 提交
4. 复制 key，填入 `.env` 的 `AMAP_API_KEY`
5. 免费，每天有调用配额

---

## 项目结构

```
local_life_agent/
├── run_backend.py              # 一键启动
├── .env                        # 你的 API Key 配置（不要提交到 git）
├── .env.example                # 配置模板
├── backend/
│   ├── config/settings.py      # 配置 & 模式控制 (demo_real/demo_safe)
│   ├── providers/              # API 对接层（DeepSeek / 高德 / mock）
│   ├── agent/                  # Agent 核心逻辑
│   │   ├── main_agent.py              # 统一入口（当前主流程）
│   │   ├── orchestrator_v2.py         # 主编排器 (13阶段管线)
│   │   ├── stream_orchestrator.py     # 流式编排器 (SSE, 同13阶段)
│   │   ├── orchestrator_shared.py     # 共享逻辑 (scene推断/POI fallback/距离过滤)
│   │   ├── orchestrator.py            # [Legacy] V1 mock pipeline
│   │   ├── location_resolver.py       # 定位解析 (50+城市, 多级优先级)
│   │   ├── ranking.py                 # 候选排序引擎 (加权评分)
│   │   ├── plan_generator.py          # 行程构建
│   │   ├── feasibility_v2.py          # 可行性检查 (12项)
│   │   ├── action_planner_v2.py       # 动作计划生成
│   │   ├── executor_v2.py             # 工具执行 (retry + fallback)
│   │   ├── share_message_v2.py        # 分享消息生成
│   │   └── explanation.py             # LLM 方案解释 (含 markdown sanitization)
│   ├── api/                    # HTTP 接口 (REST + SSE)
│   └── tools/                  # 工具函数 (mock API)
├── frontend/                   # Web 前端（React + TypeScript）
│   └── src/
│       ├── App.tsx             # 主页面 (默认流式, 位置展示, 模式切换)
│       ├── api.ts              # API 调用 & SSE 解析
│       └── components/         # UI 组件 (Trace/Order/Timeline)
├── data/                       # 模拟数据 (users/families/friends)
├── tests/                      # 测试
└── docs/                       # 设计文档
```

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 前端页面 |
| `GET /api/provider-status` | 查看当前 Provider 模式 (基本) |
| `GET /api/provider/status` | 查看详细 Provider 状态 (含 safe_for_live_demo) |
| `POST /api/mode/switch` | 运行时切换模式 (demo_real ↔ demo_safe) |
| `POST /api/plan` | **主规划接口** (当前 V2 pipeline) |
| `POST /api/plan/stream` | **主流式接口** (SSE, 默认使用) |
| `POST /api/plan/v2` | 兼容接口 (等同于 /api/plan) |
| `POST /api/plan/v2/stream` | 兼容接口 (等同于 /api/plan/stream) |

### 示例请求

```bash
# 主接口
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"带孩子去公园玩，3个人，想吃川菜"}'

# 带定位 + demo scenario
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"下午带孩子出去玩","location":{"source":"manual","address":"上海徐汇区"},"demo_scenario":"restaurant_full"}'

# 流式接口
curl -X POST http://localhost:8000/api/plan/stream \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"下午带老婆孩子出去玩"}'
```

---

## 早期 V1 Mock Pipeline（Legacy）

早期 V1 mock pipeline 已保留为 legacy fallback（`backend/agent/orchestrator.py`），仅用于测试和 mock 工具复用。当前主流程是上述的 Local Life Agent Pipeline（`main_agent.py` → `orchestrator_v2.py` / `stream_orchestrator.py`），包含完整的 provider 抽象、真实 API 集成、流式输出、13 阶段管线、可行性检查和动作执行。

---

## 运行测试

```bash
python -m pytest tests/ -v
```

---

## 常见问题

**Q: 前端页面打不开，显示 JSON？**
A: 先运行 `cd frontend && npm run build` 构建前端，再启动后端。

**Q: 改了 .env 没生效？**
A: 可以直接用前端模式切换开关，或重启后端。前端切换无需重启。

**Q: demo_real 模式启动报错？**
A: demo_real 模式下如果 API key 缺失会自动降级为 mock，不会报错。如需强制使用真实 API，确保 `.env` 里两个 key 都存在。

**Q: 推荐结果里评分、人均显示 unknown？**
A: 这是预期行为。高德地图 API 不返回餐厅评分和人均消费，这些字段如实标记为 unknown，不会编造数据。

**Q: 流式输出不工作？**
A: 前端默认使用流式输出。如果流式连接失败，会自动 fallback 到普通模式。某些浏览器可能对 SSE 有兼容性问题，推荐使用 Chrome/Edge。

**Q: 定位不准确？**
A: 浏览器定位精度取决于设备和网络环境。可以手动选择出发地，或在 query 中说明当前位置（如"我在湖州市"），系统会自动识别。

**Q: 方案里出现了其他城市的 POI？**
A: 系统已内置距离过滤（80km），自动拒绝与出发地距离过远的候选。如仍出现异常结果，通常是 mock fallback 数据需要更新该城市的默认坐标。
