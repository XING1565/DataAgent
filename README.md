# DataAgent

DataAgent 是一个面向表格数据的智能分析工作台示例项目。它提供 CSV/XLSX 数据上传、字段概要、数据预览、自然语言分析、图表生成、追问上下文和 Markdown 报告生成能力。

项目由 FastAPI 后端和 React/Vite 前端组成，后端集成 LangGraph、PandasAI、Plotly/Matplotlib，并可通过 OpenAI 兼容接口接入 DashScope 等大模型服务。

## 功能概览

- 数据集管理：上传 CSV/XLSX 文件，生成字段结构、预览数据和质量摘要。
- 自然语言分析：通过聊天方式对数据提问，例如趋势分析、区域对比、异常识别。
- 图表与表格结果：优先返回图表产物，必要时回退为表格结果和提示信息。
- 多轮上下文：同一 `session_id` 下支持基于前文继续追问。
- 报告生成：根据分析会话生成 Markdown 报告。
- 前端工作台：包含上传、数据预览、聊天分析、结果展示、报告中心等模块。
- Docker 部署：提供后端 API 的 Docker Compose 启动方式。

## 技术栈

- 后端：FastAPI、Pydantic、LangGraph、PandasAI、pandas、FastMCP
- 图表：Matplotlib、Plotly
- 前端：React 19、Vite 7、TypeScript、Tailwind CSS、lucide-react
- 测试：pytest、httpx
- 运行环境：建议 Python 3.11

## 目录结构

```text
.
├── backend/              # FastAPI 后端应用、API、服务、图分析流程和测试
├── frontend/             # React/Vite 前端工作台
├── data/                 # 本地数据、上传文件、会话、任务和图表产物
├── demo/                 # 演示数据
├── exports/              # 导出文件
├── docker-compose.yml    # 后端 Docker Compose 配置
├── requirements.txt      # Python 依赖
└── README.md
```

## 环境准备

建议使用 Python 3.11，以兼容 PandasAI v3。

```powershell
conda create -n dataagent-py311 python=3.11 -y
conda activate dataagent-py311
python -m pip install -r requirements.txt
```

复制环境变量模板并填写模型服务配置：

```powershell
Copy-Item .env.example .env
```

DashScope OpenAI 兼容模式示例：

```env
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
PANDASAI_LLM_MODEL=openai/qwen-plus
```

## 本地启动后端

```powershell
conda activate dataagent-py311
cd backend
pip install requirements.txt
python run.py
```

启动后可访问：

```text
API 文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/health
```

## 启动前端工作台

请先启动后端 API，然后在另一个终端运行：

```powershell
cd frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

如需指定后端地址：

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## Docker Compose 启动

Docker Compose 会构建并启动后端 API，读取根目录 `.env`，并将本地 `data/` 挂载到容器内。

```powershell
docker compose up --build
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```


## 常用接口

- `GET /health`：健康检查
- `POST /api/v1/datasets`：上传数据集
- `POST /api/v1/chat`：发送自然语言分析请求
- `POST /api/v1/reports`：根据会话生成报告
- `/docs`：Swagger API 文档

## 测试与构建

后端测试：

```powershell
$env:PYTHONPATH="backend"
python -m pytest backend/tests
```

前端构建：

```powershell
cd frontend
npm run build
```

## 数据与产物说明

- 上传文件保存在 `data/uploads/`。
- 数据集元信息保存在 `data/datasets/`。
- 会话信息保存在 `data/sessions/`。
- Agent 事件保存在 `data/agent_events/`。
- 图表和报告相关产物保存在 `data/artifacts/` 与 `exports/`。

这些目录用于本地演示和开发调试。生产部署时建议根据实际需求替换为数据库、对象存储或更完整的任务队列。

