# Local Life Planning Agent

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
# 必填：运行模式（demo 模式需要真实 API）
APP_MODE=demo

# DeepSeek API Key — 用于理解你的自然语言需求
# 免费注册获取：https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-你的key

# 高德地图 API Key — 用于搜索地点、路线、天气
# 免费注册获取：https://console.amap.com/dev/key/app
AMAP_API_KEY=你的key
```

> **没有 API Key 也能跑：** 把 `APP_MODE` 改成 `development`，系统会用模拟数据运行。

### 3. 启动

```bash
python run_backend.py
```

浏览器打开 **http://localhost:8000**，输入需求，点"开始规划"。

---

## 三种运行模式

| 模式 | 用途 | 需要 API Key？ |
|------|------|:---:|
| `demo` | 比赛展示 / 正式使用 | ✅ 两个都需要 |
| `development` | 本地开发 | ❌ 没有 Key 自动用模拟数据 |
| `test` | 跑自动化测试 | ❌ 强制模拟 |

切换模式只需改 `.env` 里的 `APP_MODE`，重启即可。

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
├── run_backend.py          # 一键启动
├── .env                    # 你的 API Key 配置（不要提交到 git）
├── .env.example            # 配置模板
├── backend/
│   ├── config/settings.py  # 配置 & 模式控制
│   ├── providers/          # API 对接层（DeepSeek / 高德）
│   ├── agent/              # Agent 核心逻辑（解析 → 搜索 → 评分 → 规划）
│   ├── api/                # HTTP 接口
│   └── tools/              # 工具函数
├── frontend/               # Web 前端（React + TypeScript）
├── data/                   # 旧版模拟数据（兼容保留）
├── tests/                  # 测试
└── docs/                   # 设计文档
```

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 前端页面 |
| `GET /api/provider-status` | 查看当前用的真实 API 还是模拟数据 |
| `POST /api/plan` | 旧版规划接口 |
| `POST /api/plan/v2` | **新版规划接口（推荐）** |

### 示例请求

```bash
curl -X POST http://localhost:8000/api/plan/v2 \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_001","query":"带孩子去公园玩，3个人，想吃川菜"}'
```

## 运行测试

```bash
python -m pytest tests/ -v
```

---

## 常见问题

**Q: 前端页面打不开，显示 JSON？**
A: 先运行 `cd frontend && npm run build` 构建前端，再启动后端。

**Q: 改了 .env 没生效？**
A: 重启后端即可。每次启动时会重新读取 `.env`。

**Q: demo 模式启动报错？**
A: 检查 `.env` 里的 `DEEPSEEK_API_KEY` 和 `AMAP_API_KEY` 是否都填了，不能为空。

**Q: 推荐结果里评分、人均显示 unknown？**
A: 这是预期行为。高德地图 API 不返回餐厅评分和人均消费，这些字段如实标记为 unknown，不会编造数据。
