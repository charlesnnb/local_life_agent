# Local Life Agent

一句自然语言生成可执行的本地生活行程：理解需求、拆分任务、搜索地点、
安排路线与时间线，并明确展示模拟点餐、预约和分享消息。

## 推荐运行方式

### 评委本地运行：Demo Mode

```bash
./run.sh demo
```

- 不需要任何 API Key
- 不调用外部网络
- 使用规则任务规划、本地 POI/路线和 Mock Actions
- 无高德 JS Key 时显示离线路线图

确定性异常场景：

```bash
./run.sh demo restaurant_full       # 餐厅无座，触发备选方案
./run.sh demo activity_unavailable  # 活动关闭，触发同类替换
./run.sh demo traffic_delay         # 路线拥堵，触发时间调整
```

### 比赛视频录制：Hybrid Live Mode

在 `.env` 和 `frontend/.env` 中填入 API Key（这两个文件已被 Git 忽略）：

```env
# .env
DEEPSEEK_API_KEY=your_key
AMAP_WEB_SERVICE_KEY=your_key

# frontend/.env
VITE_AMAP_JS_KEY=your_key
VITE_AMAP_SECURITY_JS_CODE=your_code
```

```bash
./run.sh hybrid
```

Hybrid 使用真实 DeepSeek、AMap POI、AMap Route 和 AMap JS 地图；点餐、
预约、支付和消息发送仍是 Mock。任何真实 provider 失败都会回退，不中断规划。

录制预约失败场景：

```bash
./run.sh hybrid restaurant_full
```

### 可选：Live Mode

```bash
./run.sh live
```

当前没有真实 Action Provider。Live 会明确显示 `Mock fallback`，不会伪装成
真实下单、预约、支付或微信发送。

只检查配置：

```bash
./run.sh demo --check
./run.sh hybrid --check
./run.sh live --check
```

Launcher 固定使用：

- 前端：http://localhost:5173
- 后端：http://localhost:8000

端口已被旧进程占用时会直接报错，避免新前端连接旧后端。

## 三种运行模式

| 模式 | LLM | POI / Route / Map | Actions | 用途 |
| --- | --- | --- | --- | --- |
| Demo | Rule / Mock | Mock / 离线路线图 | Mock | 评委、断网、零 Key |
| Hybrid | DeepSeek | AMap | Mock | 视频录制 |
| Live | DeepSeek | AMap | Mock fallback | 未来真实 Action 扩展 |

页面会显示实际来源。真实 API 失败时可看到 `Rule fallback` 或
`Mock fallback`，不会把 fallback 数据标成真实服务。

## 环境变量

参考 `.env.example` 和 `frontend/.env.example`。

后端实际读取的变量（通过 `src/config/settings.py`）：

- `RUN_MODE` — 运行模式（demo / hybrid / live），由 `run.sh` 自动设置
- `DEEPSEEK_API_KEY` — DeepSeek API Key（Hybrid / Live 需要）
- `AMAP_WEB_SERVICE_KEY` — 高德 Web Service Key（Hybrid / Live 需要）
- 其余变量见 `.env.example`

前端实际读取的变量：

- `VITE_AMAP_JS_KEY` — 高德 JS API Key（Hybrid / Live 需要）
- `VITE_AMAP_SECURITY_JS_CODE` — 高德 JS API 安全密钥（可选）

三种模式的具体行为由 `run.sh` 管理，不需要多份 example 文件。

## 页面结构

- `/`：主规划页面
- `/settings`：四步偏好问卷

首页默认突出输入和最终方案。完整 Agent 日志、候选过滤和 provider 技术详情
均默认折叠。偏好保存在后端内存 profile 中；浏览器只记录问卷是否完成。

## 推荐输入

家庭亲子：

```text
今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥
```

多阶段任务：

```text
今天早上想去公园玩，中午点个肯德基外卖，下午去打台球，晚上去喝茶
```

预约失败：

```text
今天下午去看展，晚上吃火锅，最好提前预约，不想排队
```

## API

```text
GET  /api/runtime
GET  /api/preferences/default
GET  /api/preferences/current
POST /api/preferences
POST /api/plan
POST /api/plan/stream
POST /api/replan/confirm
```

调用示例：

```bash
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"query":"今天下午带孩子出去玩，晚上吃清淡一点"}'
```

架构和数据边界见 [docs/design.md](docs/design.md)。

## 开发与测试

```bash
pip install -r requirements.txt

cd frontend
npm install
cd ..

python -m pytest

cd frontend
npm test
npm run build
```

单独启动后端：

```bash
python run_backend.py
```

单独启动前端：

```bash
cd frontend
npm run dev -- --mode demo
```

## Mock 与真实能力边界

- `source=amap` 只表示地点身份或路线来自高德。
- 价格、排队、儿童友好、饮食标签和预约能力属于 Mock Local Commerce。
- `mock_success` 是模拟成功，不代表真实交易。
- `mock_failed` 是模拟失败，页面会显示原因和备选方案。
- 项目不接 MCP、美团交易、真实支付或微信发送。
- Demo 快捷按钮只填充输入，不返回预置答案。
- 所有模式继续使用同一个 `PlannerAgent.run(...)` 主流程。

### 异常处理

三类异常均需用户确认后才更新方案：

- **餐厅无座** — 模拟预约失败 → 提供附近备选餐厅
- **活动不可用** — 活动关闭或无票 → 提供同类替换活动
- **路线拥堵 / 时间冲突** — 提供调整预约或保留原方案

### API Fallback

| 能力 | Hybrid 首选来源 | Fallback |
| --- | --- | --- |
| 意图与任务规划 | DeepSeek | Rule fallback |
| POI 和餐厅身份 | AMap | 本地 Mock 数据 |
| 路线估算 | AMap Route | 离线估算 |
| 地图展示 | AMap JS API | 离线路线图 |
| 点餐、预约、消息 | Mock | Mock 失败并说明原因 |
