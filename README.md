# Local Life Agent

一句自然语言生成可执行的本地生活行程：理解需求、拆分任务、搜索地点、规划路线与时间线，并处理点餐、预约、消息和异常重规划。

系统会把用户输入拆成有顺序的生活任务，调用 LLM 和高德完成需求理解、地点搜索和路线规划，最终生成时间线、地图以及可执行动作。README 中的 DeepSeek 配置只是一个示例，用户可以替换为自己的兼容模型服务。

## 核心功能

- 自然语言意图理解与多任务拆解
- 高德 POI 搜索、路线规划和地图展示
- 用户偏好与任务相关性排序
- 可执行时间线和路线生成
- 点餐、预约和分享消息模拟
- 餐厅无座、活动不可用、路线冲突三类异常处理
- 外部 API 失败时自动降级

## 快速开始

```bash
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

## 运行项目

### Hybrid Mode（推荐）

Hybrid Mode 使用真实 LLM、高德地点搜索、路线规划和地图；点餐、预约和消息发送使用 Mock。下面以 DeepSeek 作为 OpenAI-style LLM Provider 示例，用户可以按需替换为自己的模型服务。

在 `.env` 和 `frontend/.env` 中填入 API Key（这两个文件已被 Git 忽略）：

```env
# .env
DEEPSEEK_API_KEY=your_key
AMAP_WEB_SERVICE_KEY=your_key
```

```env
# frontend/.env
VITE_AMAP_JS_KEY=your_key
VITE_AMAP_SECURITY_JS_CODE=your_code
```

启动：

```bash
./run.sh hybrid
```

访问：

- Frontend: http://localhost:5173
- Backend:  http://localhost:8000

如果 LLM 或高德请求失败，系统会自动使用规则或本地数据继续规划。

### 其他模式

```bash
./run.sh demo
```

Demo Mode 不需要 API Key，使用本地数据，适合离线运行和评审验证。

```bash
./run.sh live
```

Live Mode 为真实 Action Provider 预留；目前点餐、预约、支付和消息发送仍会明确标记为 Mock 或 fallback。

点餐、预约、支付和消息发送为模拟能力，页面会明确显示 Mock 状态，不代表真实交易。

## 推荐输入

家庭亲子：

```text
今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥
```

多阶段任务：

```text
今天早上想去公园玩，中午点个肯德基外卖，下午去打台球，晚上去喝茶
```

异常处理：

```text
今天下午去看展，晚上吃火锅，最好提前预约，不想排队
```

Demo Mode 可通过 `restaurant_full`、`activity_unavailable` 和 `traffic_delay` 参数稳定复现三类异常。

## 页面

- `/`：行程规划、时间线、地图和模拟动作
- `/settings`：用户偏好问卷

## 测试

```bash
python -m pytest

cd frontend
npm test
npm run build
```

Backend API documentation is available through FastAPI at `/docs`.

## 评审材料

- 设计文档 PDF：`docs/设计文档.pdf`
- Demo 视频：[点击查看](https://drive.google.com/file/d/1ZqtGIUsDz3kzjgpTPfp_kLp4nMgCHNqk/view)
- 文字版设计说明：[docs/design.md](docs/design.md)
