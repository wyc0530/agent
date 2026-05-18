# 学习辅助系统 (Learning Assistant System)

基于 LangGraph 的多智能体学习辅助系统，为学生提供全方位的学习支持。

## 系统架构

```
┌─────────────────────────────────────────────┐
│              前端 (Web UI)                   │
└──────────────────┬──────────────────────────┘
                   │ FastAPI
┌──────────────────▼──────────────────────────┐
│           Agent 7: 助教 (Supervisor)         │
│        路由决策 → 调度其他 6 个 Agent          │
└──┬─────┬─────┬─────┬─────┬─────┬────────────┘
   │     │     │     │     │     │
   ▼     ▼     ▼     ▼     ▼     ▼
 学习  学习  学习  个性  复习  考试
 规划  专家  伙伴  出题  整理  指导
```

### 七个智能体

| Agent | 名称 | 功能 | 构建范式 |
|-------|------|------|----------|
| 1 | 学习规划 | 制定个性化学习方案 | Plan-and-Solve |
| 2 | 学习专家 | 推荐课程资料和学习内容 | ReAct |
| 3 | 学习伙伴 | 在线答疑 + 专注时间 | ReAct |
| 4 | 个性化出题 | 基于历史的个性化出题 + 能力测评 | Reflection |
| 5 | 复习整理 | 错题分析 + 易错点生成 | Reflection |
| 6 | 考试指导 | 考试和实践指导 | Plan-and-Solve |
| 7 | 助教 | 统一对话入口，调度其他 Agent | Supervisor |

### 技术栈

- **Agent 框架**: LangGraph
- **LLM**: OpenAI API / 本地模型 (Qwen2.5)
- **向量数据库**: ChromaDB
- **Embedding**: OpenAI Embedding / BGE
- **Web 框架**: FastAPI
- **前端**: Streamlit (推荐快速原型)

---

## 快速开始

### 环境要求

- Python >= 3.11
- pip >= 24.0
- 5GB+ 磁盘空间 (如果使用本地模型)

### 1. 克隆并进入项目

```bash
cd 软件杯
```

### 2. 配置虚拟环境

```bash
# 已有虚拟环境 agent-env，激活它
# Windows:
agent-env\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

编辑 `.env` 文件，填入你的 API Keys:

```ini
# 必填: LLM API Key (OpenAI 或其他兼容接口)
LLM_API_KEY=sk-your-openai-api-key

# 必填: Embedding API Key (与 LLM 共用或独立)
EMBEDDING_API_KEY=sk-your-openai-api-key

# 可选: 搜索 API (SerpAPI)
SERPAPI_API_KEY=your-serpapi-key
```

### 5. 验证安装

```bash
python -c "from src.config import Settings; print(Settings.display())"
```

### 6. 启动服务

```bash
python -m src.api.main
# 或
uvicorn src.api.main:app --reload
```

访问 `http://localhost:8000/docs` 查看 API 文档。

---

## 项目结构

```
软件杯/
├── agent-env/                    # Python 虚拟环境
├── src/
│   ├── config.py                 # 配置管理
│   ├── llm.py                    # LLM 统一接入层
│   ├── embedding.py              # Embedding 模块
│   ├── core/
│   │   ├── state.py              # 全局 State Schema
│   │   ├── memory.py             # 记忆模块 (向量存储 + 长期记忆)
│   │   ├── retriever.py          # 检索模块 (RAG)
│   │   ├── communication.py      # Agent 间通信
│   │   └── tools/
│   │       ├── base.py           # 工具基类 + 注册机制
│   │       ├── search.py         # Web 搜索工具
│   │       ├── timer.py          # 专注计时工具
│   │       └── document.py       # 文档生成工具
│   ├── agents/                   # 7 个 Agent (Phase 2+)
│   └── api/
│       └── main.py               # FastAPI 应用
├── tests/
│   └── test_core.py              # 基础设施集成测试
├── data/
│   ├── vector_store/             # ChromaDB 持久化
│   └── checkpoints/              # LangGraph Checkpoints
├── .env                          # 环境变量配置
├── requirements.txt              # Python 依赖
└── README.md                     # 本文档
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查，验证所有组件状态 |
| POST | `/chat` | 对话接口 |
| POST | `/search` | 检索增强搜索 |
| POST | `/embed` | 文本向量化 |
| GET | `/tools` | 可用工具列表 |
| POST | `/memory/store` | 存储记忆到向量库 |

---

## 配置参数说明

### LLM 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `openai` | LLM 提供商 |
| `LLM_API_KEY` | - | API 密钥 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `LLM_TEMPERATURE` | `0.7` | 温度参数 (0-2) |
| `LLM_MAX_TOKENS` | `4096` | 最大输出 token |

### 本地 LLM (备选)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LOCAL_LLM_ENABLED` | `false` | 是否启用本地模型 |
| `LOCAL_LLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 模型名称 |
| `LOCAL_LLM_DEVICE` | `cpu` | 运行设备 |
| `LOCAL_LLM_QUANTIZATION` | `int8` | 量化方式 |

### Embedding 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | `openai` | Embedding 提供商 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 模型名称 |

### 向量数据库

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VECTOR_DB_TYPE` | `chromadb` | 数据库类型 |
| `CHROMA_PERSIST_DIR` | `./data/vector_store` | 持久化目录 |
| `CHROMA_COLLECTION_NAME` | `learning_assistant` | 集合名称 |

### 记忆模块

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MEMORY_MAX_MESSAGES` | `50` | 最大对话消息数 |
| `MEMORY_SUMMARY_ENABLED` | `true` | 是否启用对话摘要 |
| `CHECKPOINT_STORE_PATH` | `./data/checkpoints` | Checkpoint 路径 |

---

## 本地模型部署 (可选)

当 API 不可用时的备选方案:

### 本地 LLM

```bash
# 方式1: 使用 Ollama
ollama pull qwen2.5:7b
# 将 LLM_BASE_URL 设置为 http://localhost:11434/v1

# 方式2: 使用 LM Studio 或 text-generation-webui
# 启动后修改 LOCAL_LLM_ENABLED=true
```

### 本地 Embedding

```bash
# 自动下载 (首次使用)
pip install sentence-transformers
# 修改 LOCAL_EMBEDDING_ENABLED=true
# 模型将自动下载到 LOCAL_EMBEDDING_PATH
```

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试模块
pytest tests/test_core.py -v

# 运行不带 API Key 的测试 (离线模式)
pytest tests/test_core.py -v -k "not api_key"

# 覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

---

## 下一步: Phase 2 - Agent 构建

基础设施层完成后，按以下顺序构建 7 个 Agent:

1. **Agent 1 - 学习规划** (Plan-and-Solve)  
   - `src/agents/planner.py`
2. **Agent 2 - 学习专家** (ReAct)  
   - `src/agents/expert.py`
3. **Agent 3 - 学习伙伴** (ReAct)  
   - `src/agents/partner.py`
4. **Agent 4 - 个性化出题** (Reflection)  
   - `src/agents/quizzer.py`
5. **Agent 5 - 复习整理** (Reflection)  
   - `src/agents/reviewer.py`
6. **Agent 6 - 考试指导** (Plan-and-Solve)  
   - `src/agents/examiner.py`
7. **Agent 7 - 助教** (Supervisor)  
   - `src/agents/assistant.py`