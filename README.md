# 学习辅助系统 (Learning Assistant System)

基于 **LangGraph + LLM** 构建的**智能多 Agent 协作学习追踪系统**。依托 7 个专业 Agent、向量记忆检索、反思机制与强化学习，实现从「学习规划 → 知识学习 → 练习测评 → 错题复盘 → 动态优化」的**全链路闭环**，沉淀用户长期学习数据，实现个性化自适应学习。

> **产品定位**：[PRODUCT.md](PRODUCT.md) | **设计系统**：[DESIGN.md](DESIGN.md) | **开发流程**：[开发流程.md](开发流程.md) | **Git 规范**：[git开发手册.md](git开发手册.md)

---

## 目录

- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [项目架构](#项目架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置详情](#配置详情)
- [API 接口](#api-接口)
- [前端交互层](#前端交互层)
- [使用示例](#使用示例)
- [运行测试](#运行测试)
- [Docker 部署](#docker-部署)
- [项目阶段](#项目阶段)
- [对话上下文管理](#对话上下文管理)
- [历史对话管理](#历史对话管理)
- [安全措施](#安全措施)
- [依赖项](#依赖项)
- [贡献流程](#贡献流程)
- [许可证](#许可证)
- [相关文档](#相关文档)

---

## 项目概述

学习辅助系统是一款面向自学者的 AI 驱动学习平台。用户可以与 AI 进行自然语言对话，系统通过 Supervisor 总控 Agent 智能路由到 7 个专业 Agent 之一，提供学习规划、知识讲解、练习出题、错题分析、备考指导等全方位学习支持。

系统采用 **FastAPI + SSE 流式对话** 架构，前端为纯 HTML/CSS/JS SPA 应用，后端基于 LangGraph 编排多 Agent 协作流程，支持向量检索（Qdrant）、知识图谱（Neo4j）、MySQL 用户数据持久化、对话历史管理和断点续聊。

---

## 核心功能

### 多 Agent 协作

| Agent | 角色 | 架构模式 | 核心能力 |
|-------|------|---------|---------|
| **Supervisor** | 总控调度 | 关键词 + LLM 语义路由 + LangGraph 编排 | 消息分发 → 子 Agent 调用 → 结果聚合 → 并行执行 |
| **Planner** | 学习规划师 | Plan-and-Solve | 制定个性化学习计划，生成分阶段目标 |
| **Expert** | 学习专家 | ReAct 循环 | 搜索 → 分析 → 反思 → 迭代优化，推荐学习资料，整合 Web 搜索 + 文档生成 |
| **Partner** | 学习伙伴 | RAG | 基于知识库回答提问，记录专注学习时间 |
| **Quizzer** | 出题助手 | Reflection + RL | 生成试题，评估能力，反思题目质量，自适应调整难度 |
| **Reviewer** | 错题分析师 | Reflection | 分析错题模式，整理薄弱知识点，反馈给规划 Agent |
| **Examiner** | 备考顾问 | Plan-and-Solve | 提供考试策略、模拟面试、备考规划 |

### 基础设施能力

- **多 LLM 后端支持**：OpenAI、ModelScope、智谱、DeepSeek、自定义 OpenAI 兼容接口
- **向量存储**：Qdrant（本地文件 / 远程服务器双模式）
- **知识图谱**：Neo4j（带 Cypher 注入防护）
- **MySQL 用户系统**：用户注册/登录（PBKDF2 密码哈希）、个人信息管理、对话历史持久化
- **Web 搜索**：SerpAPI + DuckDuckGo + 课程目录回退
- **文件处理**：支持 PDF/Word/TXT/代码文件上传与解析，上传进度追踪，前端双重校验
- **文档生成**：支持 Word 文档生成与下载，文件问答内容导出
- **测验引擎**：出题生成 + 能力评估 + 自适应难度调整
- **专注计时器**：记录用户学习时长
- **上下文感知对话**：对话历史摘要压缩 + 边界指令，防止重复回答
- **断点续聊**：磁盘持久化对话历史，启动自动恢复，定时保存
- **SSE 流式对话**：实时流式输出，支持 Agent 心跳保活与超时保护
- **对话历史管理**：MySQL 持久化存储，支持创建/切换/删除/重命名对话，完整展示用户提问与 AI 回复
- **响应式前端**：桌面/平板/手机三端适配，明暗主题切换，WCAG 2.1 AA 无障碍标准
- **容器化部署**：Dockerfile 多阶段构建 + docker-compose 服务编排
- **使用指南页面**：独立 guide.html 页面，含功能概述/快速上手/操作指南/FAQ/注意事项

---

## 项目架构

```
├── src/                            # 后端 Python 服务
│   ├── config.py                   # 全局配置（基于 pydantic-settings）
│   ├── llm.py                      # LLM 统一调用层（多 Provider 支持 + 流式/非流式）
│   ├── embedding.py                # 向量嵌入层（云端 + 本地双模式 + 批量缓存）
│   │
│   ├── agents/                     # Agent 模块层（7 个 Agent + 1 个 Supervisor）
│   │   ├── __init__.py             # 模块初始化 + Agent 注册
│   │   ├── base_agent.py           # Agent 基类（通用属性与方法）
│   │   ├── assistant.py            # 总控 Agent（关键词 + LLM 语义路由）
│   │   ├── planner.py              # 学习规划师（Plan-and-Solve）
│   │   ├── expert.py               # 学习专家（ReAct + WebSearch）
│   │   ├── partner.py              # 学习伙伴（RAG + FocusTimer）
│   │   ├── quizzer.py              # 出题助手（QuizGen + RL）
│   │   ├── reviewer.py             # 错题分析师（Reflection）
│   │   └── examiner.py             # 备考顾问（Plan-and-Solve）
│   │
│   ├── core/                       # 基础设施层
│   │   ├── __init__.py             # 模块初始化
│   │   ├── state.py                # 全局状态定义（AgentState / UserProfile）
│   │   ├── memory.py               # 向量存储（Qdrant 本地/远程双模式）
│   │   ├── retriever.py            # 检索层（RAG 混合检索）
│   │   ├── graph.py                # 知识图谱（Neo4j + Cypher 注入防护）
│   │   ├── communication.py        # Agent 间通信（消息路由与聚合）
│   │   ├── checkpoint.py           # 对话存档（JSON 持久化 + 自动恢复）
│   │   ├── user_store.py           # 用户管理（MySQL 连接池 + 对话历史 CRUD）
│   │   ├── file_processor.py       # 文件处理（上传/解析/存储，支持 PDF/Word/TXT/代码）
│   │   ├── word_generator.py       # Word 文档生成器（问答导出 + 文件问答下载）
│   │   └── tools/                  # 工具库
│   │       ├── __init__.py         # 工具模块初始化
│   │       ├── base.py             # 工具基类 + ToolRegistry 注册中心
│   │       ├── search.py           # Web 搜索工具（SerpAPI / DuckDuckGo）
│   │       ├── timer.py            # 专注计时器
│   │       ├── document.py         # 文档生成器（Word 文档）
│   │       └── quiz.py             # 出题引擎 + 能力评估
│   │
│   └── api/                        # API 服务层
│       ├── __init__.py             # 模块初始化
│       └── main.py                 # FastAPI 服务（28 个端点 + SSE 流式 + 中间件）
│
├── frontend/                       # 前端（HTML/CSS/JS SPA）
│   ├── index.html                  # 主入口，SPA 单页面
│   ├── guide.html                  # 使用指南页面（功能概述/操作指南/FAQ/注意事项）
│   ├── package.json                # 前端依赖管理
│   ├── vitest.config.js            # 前端测试配置
│   ├── css/                        # 样式表（8 个文件）
│   │   ├── variables.css           # CSS 自定义属性（色彩/字体/间距/圆角）
│   │   ├── base.css                # 全局重置与基础样式
│   │   ├── layout.css              # 页面布局（栅格 + Flex）
│   │   ├── auth.css                # 登录/注册卡片
│   │   ├── chat.css                # 聊天消息与输入区域
│   │   ├── sidebar.css             # 侧边栏组件
│   │   ├── guide.css               # 指南页面样式（响应式 + 暗色模式）
│   │   └── responsive.css          # 响应式适配 + 暗色模式
│   ├── js/                         # JavaScript 模块（11 个文件）
│   │   ├── state.js                # 全局状态管理（localStorage + sessionStorage）
│   │   ├── utils.js                # 工具函数（DOM 操作/表单校验/防抖/HTML 转义）
│   │   ├── api.js                  # API 客户端（统一封装 REST 调用 + XHR 文件上传）
│   │   ├── sse.js                  # SSE 流式请求（fetch + ReadableStream）
│   │   ├── toast.js                # 消息提示（info/success/error/warning）
│   │   ├── theme.js                # 主题切换（明暗模式 + 系统偏好跟随）
│   │   ├── auth.js                 # 认证模块（登录/注册/退出/密码修改）
│   │   ├── conversations.js        # 对话管理（创建/切换/删除/重命名/列表加载）
│   │   ├── chat.js                 # 聊天交互（消息渲染/SSE 流式/Markdown 解析/文件上传/进度显示）
│   │   ├── sidebar.js              # 侧边栏模块（用户信息/设置/Agent 选择/快捷操作）
│   │   └── app.js                  # 应用入口（路由管理/初始化）
│   └── tests/                      # 前端测试（9 个文件）
│       ├── setup.js                # 测试环境初始化（DOM Mock）
│       ├── state.test.js           # 状态管理测试
│       ├── utils.test.js           # 工具函数测试
│       ├── api.test.js             # API 客户端测试
│       ├── sse.test.js             # SSE 解析测试
│       ├── toast.test.js           # 提示消息测试
│       ├── auth.test.js            # 认证模块测试
│       ├── chat.test.js            # 聊天模块测试
│       └── sidebar.test.js         # 侧边栏测试
│
├── tests/                          # 后端测试
│   ├── __init__.py                 # 测试模块初始化
│   ├── conftest.py                 # 全局测试夹具（Fixtures）
│   ├── test_core.py                # 基础设施测试（Config/LLM/Embedding/Tools）
│   ├── test_agents.py              # Agent 模块测试（7 个 Agent 初始化与调用）
│   ├── test_coverage_boost.py      # 覆盖率补充测试
│   ├── test_e2e.py                 # 端到端测试（完整学习流程）
│   ├── test_context_aware.py       # 上下文感知测试
│   └── test_phase5.py              # Phase 5 安全加固测试
│
├── .trae/documents/                # 项目文档
│   ├── PRD.md                      # 产品需求文档
│   ├── TECHNICAL_ARCHITECTURE.md   # 技术架构文档
│   ├── DEPLOYMENT_GUIDE.md         # 部署指南
│   ├── COMPONENT_DOCUMENTATION.md  # 前端组件文档
│   ├── TEST_REPORT.md              # 测试报告
│   └── USER_MANUAL.md              # 用户使用手册
│
├── data/                           # 数据存储（gitignore）
├── Dockerfile                      # 多阶段构建
├── docker-compose.yml              # 服务编排（API + Qdrant + Neo4j）
├── .env.example                    # 环境变量模板（40+ 配置项）
├── .gitignore                      # Git 忽略规则
├── requirements.txt                # Python 依赖清单
├── PRODUCT.md                      # 产品定位与品牌人格
├── DESIGN.md                       # 设计系统规范
├── 开发流程.md                      # 开发流程与架构设计
└── git开发手册.md                   # Git 团队协作规范
```

---

## 技术栈

### 后端

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | 异步 Web 服务，自动生成 Swagger 文档 |
| Agent 框架 | LangGraph | 多 Agent 编排与状态管理 |
| LLM 集成 | LangChain + OpenAI SDK | 多 Provider 统一调用层 |
| 向量数据库 | Qdrant | 本地/远程双模式，语义检索 |
| 图数据库 | Neo4j | 知识图谱存储与查询 |
| 关系数据库 | MySQL | 用户数据与对话历史持久化 |
| 数据验证 | Pydantic v2 | 请求/响应模型验证 |
| 测试框架 | pytest + pytest-cov | 单元测试 + 覆盖率报告 |

### 前端

| 类别 | 技术 | 说明 |
|------|------|------|
| 架构 | SPA（单页面应用） | 基于 hash 路由，无框架依赖 |
| Markdown | marked.js | 消息渲染 |
| 数学公式 | KaTeX | LaTeX 数学公式渲染 |
| 测试框架 | Vitest + jsdom | 单元测试 + DOM 模拟 |

---

## 快速开始

### 环境要求

- **Python** 3.10+
- **Node.js** 18+（仅前端开发/测试需要）
- **MySQL** 8.0+（用户数据与对话历史存储）
- **Qdrant**（可选，默认使用本地文件模式）
- **Neo4j**（可选，仅知识图谱功能需要）

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd agent

# 安装 Python 依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写必填配置项：
#   - LLM_API_KEY：LLM API 密钥（必填）
#   - MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE：MySQL 连接信息（必填）
#   - JWT_SECRET_KEY：JWT 签名密钥（必填，生产环境请使用随机字符串）
```

### 启动服务

```bash
# 启动后端 API 服务（默认端口 8000）
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端开发服务器（另开终端，默认端口 3000）
cd frontend
python -m http.server 3000
```

启动后访问：
- **API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health
- **前端界面**：http://localhost:3000
- **使用指南**：http://localhost:3000/guide.html

---

## 配置详情

所有配置项通过 `.env` 文件管理，完整模板见 [.env.example](.env.example)。以下是核心配置分类：

### LLM 大语言模型

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商（openai / modelscope / zhipu / deepseek / custom） | `openai` |
| `LLM_API_KEY` | LLM API 密钥 | **必填** |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` |
| `LLM_BASE_URL` | 自定义 API 地址 | `https://api.openai.com/v1` |
| `LLM_TEMPERATURE` | 生成温度（0.0-2.0） | `0.7` |
| `LLM_MAX_TOKENS` | 最大输出 Token 数 | `4096` |

### Embedding 向量嵌入

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EMBEDDING_PROVIDER` | 提供商（bailian / local / openai） | `bailian` |
| `DASHSCOPE_API_KEY` | 百炼 API 密钥 | 需 Embedding 时必填 |
| `EMBEDDING_MODEL` | 模型名称 | `text-embedding-v3` |
| `EMBEDDING_DIMENSION` | 向量维度 | `1024` |

### MySQL 数据库

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_HOST` | MySQL 主机地址 | `localhost` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户名 | `root` |
| `MYSQL_PASSWORD` | MySQL 密码 | **必填** |
| `MYSQL_DATABASE` | 数据库名称 | `users` |
| `MYSQL_POOL_SIZE` | 连接池大小 | `10` |

### Qdrant 向量数据库

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QDRANT_URL` | 远程 Qdrant 地址 | `http://localhost` |
| `QDRANT_PORT` | Qdrant 服务端口 | `6333` |
| `QDRANT_USE_LOCAL` | 是否使用本地文件模式 | `true` |
| `QDRANT_LOCAL_PATH` | 本地数据存储路径 | `./data/qdrant_store` |

### Neo4j 图数据库

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | `password` |

### 服务器与安全

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |
| `DEBUG` | 调试模式 | `false` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `ALLOWED_ORIGIN` | CORS 受信来源域名 | `localhost` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | **必填** |
| `JWT_EXPIRATION_HOURS` | Token 过期时间（小时） | `24` |

> 完整配置项（40+）请查看 [.env.example](.env.example)。

---

## API 接口

系统提供 **28 个 API 端点**，覆盖 Agent 调用、LLM 对话、工具执行、记忆检索、知识图谱、用户管理、对话管理、文件处理等全部功能。

### Agent 调用

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 非流式对话（同步响应） |
| `POST` | `/chat/stream` | SSE 流式对话（支持上下文感知 + 断点续聊） |
| `POST` | `/chat/export` | 导出对话内容为 Word 文档 |
| `POST` | `/search` | Web 搜索 |
| `POST` | `/embed` | 文本向量嵌入 |

### 工具与记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/tools` | 获取可用工具列表 |
| `POST` | `/memory/store` | 存储记忆到向量库 |
| `GET` | `/graph/stats` | 知识图谱统计信息 |
| `POST` | `/graph/search` | 知识图谱搜索 |
| `POST` | `/graph/path` | 知识图谱路径查询 |

### 用户认证

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/auth/register` | 用户注册 |
| `POST` | `/auth/login` | 用户登录 |
| `POST` | `/auth/logout` | 用户登出 |

### 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/user/profile` | 获取用户个人信息 |
| `PUT` | `/user/profile` | 更新个人信息 |
| `PUT` | `/user/profile/password` | 修改密码 |
| `POST` | `/user/progress` | 更新学习进度 |
| `GET` | `/user/progress` | 获取学习进度 |

### 对话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/conversations` | 获取用户对话列表 |
| `POST` | `/conversations` | 创建新对话 |
| `GET` | `/conversations/{conv_id}` | 获取对话详情（含消息列表） |
| `PUT` | `/conversations/{conv_id}/title` | 重命名对话标题 |
| `DELETE` | `/conversations/{conv_id}` | 删除对话 |
| `DELETE` | `/conversations/{conv_id}/messages/{msg_id}` | 删除对话中的单条消息 |

### 文件处理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/file/upload` | 上传文件并解析内容（支持 PDF/Word/TXT/代码） |
| `POST` | `/file/ask` | 基于已上传文件内容进行问答 |
| `GET` | `/file/download/{filename}` | 下载生成的 Word 文档 |

访问 http://localhost:8000/docs 查看完整 Swagger 交互文档。

---

## 前端交互层

前端采用纯 HTML/CSS/JavaScript 技术栈，模块化组件架构，通过 [frontend/js/api.js](frontend/js/api.js) 统一封装后端 API 调用。主入口 [frontend/index.html](frontend/index.html) 为 SPA 单页面应用，[frontend/guide.html](frontend/guide.html) 为独立使用指南页面。

### 模块依赖关系

```
app.js (入口)
├── state.js (状态管理，无依赖)
├── utils.js (工具函数，无依赖)
├── api.js → state.js
├── sse.js → api.js, utils.js
├── toast.js → utils.js
├── theme.js → utils.js
├── conversations.js → state.js, api.js, utils.js
├── auth.js → api.js, utils.js, toast.js
├── chat.js → state.js, utils.js, api.js, sse.js, toast.js, conversations.js
└── sidebar.js → state.js, utils.js, api.js, auth.js, theme.js, conversations.js, toast.js
```

### 组件说明

| 组件 | 文件 | 功能 |
|------|------|------|
| 状态管理 | `state.js` | 全局状态（认证/消息/资料/Agent/对话），localStorage + sessionStorage 持久化 |
| 工具函数 | `utils.js` | DOM 操作、表单校验、HTML 转义、防抖节流、JSON 安全解析 |
| API 客户端 | `api.js` | 封装所有 REST API 调用（认证/用户/对话/聊天/文件上传/SSE） |
| SSE 流式 | `sse.js` | 基于 fetch + ReadableStream 实现 POST SSE 流式对话 |
| 消息提示 | `toast.js` | 浮动 Toast 通知（info/success/error/warning） |
| 主题切换 | `theme.js` | 明暗主题切换，支持系统偏好跟随与 localStorage 持久化 |
| 认证模块 | `auth.js` | 登录/注册/退出/密码修改交互流程 |
| 对话管理 | `conversations.js` | 对话创建/切换/删除/重命名/列表加载，消息完整性校验 |
| 聊天模块 | `chat.js` | 消息渲染、SSE 流式更新、Markdown + KaTeX 解析、文件上传与进度显示、快捷触发 |
| 侧边栏 | `sidebar.js` | 用户信息、设置表单、Agent 选择器、测验生成、快捷操作 |
| 应用入口 | `app.js` | 路由管理（#login/#chat）、初始化、鉴权守卫 |

### SSE 流式对话机制

```
用户发送消息
    │
    ├── 前端：POST /chat/stream (fetch + ReadableStream)
    │       解析 SSE 事件流 (start/chunk/done/error)
    │
    ├── 后端：Supervisor 路由 → 子 Agent 执行
    │       每个 chunk: SSE("chunk", {content: "..."})
    │       完成: SSE("done", {agent_role: "planner"})
    │       错误: SSE("error", {content: "..."})
    │
    └── 前端：逐字更新 DOM + 光标动画
             完成后保存到消息历史 + 对话列表
```

### 对话历史管理流程

```
用户打开对话列表
    │
    ├── GET /conversations → 获取所有对话（标题/更新时间/消息数）
    │
    ├── 点击对话 → GET /conversations/{id} → 加载完整消息列表
    │       └── 前端渲染：用户消息（右对齐）+ AI 回复（左对齐）
    │
    ├── 新建对话 → POST /conversations → 创建空对话
    │       └── 发送消息 → SSE 流式 → 自动关联到当前对话
    │
    └── 管理操作 → 重命名 / 删除对话
```

### 设计系统

前端 UI 遵循极简暖灰白基调设计系统，详细规范见 [DESIGN.md](DESIGN.md)。设计关键词：

- **色彩**：暖灰白底色 + 哑光靛蓝强调色（≤10% 交互面）
- **圆角**：柔和 8-12px，无尖锐直角
- **动效**：默认关闭，可全局开启
- **响应式**：桌面/平板/手机三端适配，支持系统暗色模式
- **无障碍**：WCAG 2.1 AA，语义化 HTML + ARIA 标签

---

## 使用示例

### 意图路由

Supervisor 根据用户消息中的关键词自动路由到合适的 Agent：

| 关键词示例 | 路由目标 |
|-----------|---------|
| 制定计划、学习计划、规划、安排 | PlannerAgent |
| 推荐、资料、课程、教材、资源 | ExpertAgent |
| 不会、怎么、什么是、解释、问题 | PartnerAgent |
| 出题、做题、题目、练习、自测、测验 | QuizzerAgent |
| 复习、错题、整理、回顾、总结、薄弱 | ReviewerAgent |
| 考试、面试、备考、应试、考研 | ExaminerAgent |

### REST API 调用

```bash
# SSE 流式对话（推荐）
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我制定Python学习计划",
    "user_id": "user_001",
    "agent_role": "planner",
    "history": [
      {"role": "user", "content": "我想学习Python"},
      {"role": "assistant", "content": "好的，让我们开始吧！"}
    ]
  }'

# 用户注册
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "xiaoming",
    "password": "secure123",
    "display_name": "小明",
    "email": "xiaoming@example.com"
  }'

# 创建对话
curl -X POST http://localhost:8000/conversations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title": "Python学习讨论"}'

# 获取对话消息
curl -X GET http://localhost:8000/conversations/<conv_id> \
  -H "Authorization: Bearer <token>"
```

---

## 运行测试

### 后端测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行含覆盖率报告
python -m pytest tests/ --cov=src --cov-report=term

# 仅运行基础设施测试
python -m pytest tests/test_core.py -v

# 仅运行 Agent 测试
python -m pytest tests/test_agents.py -v

# 运行端到端测试
python -m pytest tests/test_e2e.py -v

# 跳过需要 LLM API Key 的测试
python -m pytest -v -k "not _llm_required"
```

**当前测试状态**：290+ 测试用例 | 覆盖率 75%+ | 97%+ 通过率

### 前端测试

```bash
cd frontend
npm install
npm test

# 监听模式
npm run test:watch
```

**当前测试状态**：8 个测试文件 | 66 个测试用例 | 100% 通过率

测试文件分布：

| 文件 | 内容 | 用例数 |
|------|------|--------|
| `state.test.js` | 状态管理（Token、登录、消息、资料、Agent、对话） | 15 |
| `utils.test.js` | 工具函数（HTML 转义、表单校验、DOM 操作、防抖） | 16 |
| `api.test.js` | API 客户端（错误构造、请求头构建） | 4 |
| `sse.test.js` | SSE 解析（数据行、事件类型、容错） | 6 |
| `toast.test.js` | 消息提示（4 种类型、多条显示） | 7 |
| `auth.test.js` | 认证模块（登录、退出、Tab 切换） | 3 |
| `chat.test.js` | 聊天模块（Agent 标签、消息渲染、发送） | 5 |
| `sidebar.test.js` | 侧边栏（初始化、开关、Agent 选择、快捷操作） | 10 |

---

## Docker 部署

### 使用 Docker Compose（推荐）

```bash
# 基础模式（API + Qdrant）
docker compose up -d

# 完整模式（API + Qdrant + Neo4j）
docker compose --profile full up -d
```

### 手动构建镜像

```bash
docker build -t learning-assistant .
docker run -p 8000:8000 --env-file .env learning-assistant
```

### 前端静态部署

前端为纯静态文件，可直接部署到 Nginx 或任意 Web 服务器：

```bash
# 使用 Nginx
cp -r frontend/* /var/www/html/

# 使用 Docker + Nginx
docker run -d -p 80:80 -v $(pwd)/frontend:/usr/share/nginx/html:ro nginx:alpine
```

---

## 项目阶段

| 阶段 | 范围 | 状态 |
|------|------|------|
| **Phase 1** | 基础设施层（Config / LLM / Embedding / State / Memory / Retriever / Graph / Tools / Communication / Checkpoint / API） | 完成 |
| **Phase 2** | Agent 模块层（Planner / Expert / Partner / Quizzer / Reviewer / Examiner / Supervisor） | 完成 |
| **Phase 3** | 前端交互层（HTML/CSS/JS SPA 组件化架构 + SSE 流式对话 + 响应式适配） | 完成 |
| **Phase 4** | 测试与部署（Docker + 308 后端测试 + 66 前端测试 + E2E） | 完成 |
| **Phase 5** | 安全加固 + 上下文工程（CSRF / LLM 语义路由 / 上下文感知对话 / 断点续聊 / 对话历史管理） | 完成 |
| **Phase 6** | 文件处理系统（上传/解析/存储/问答 + Word 文档生成与导出 + 使用指南页面） | 完成 |

---

## 对话上下文管理

### 上下文感知对话

系统实现了完整的上下文感知对话机制，确保 AI 在处理新问题时：
- **参考历史对话**：自动将最近 N 轮对话历史压缩为摘要块注入系统提示
- **不重复回答**：通过边界指令防止重复输出
- **统一格式化**：所有 LLM 交互路径使用一致的摘要格式

核心实现位于 [src/api/main.py](src/api/main.py) 和 [src/llm.py](src/llm.py)。

### 断点续聊

- **自动保存**：每次追加对话消息后触发定时保存
- **启动恢复**：服务启动时自动从 `data/conversation_history.json` 恢复历史数据
- **消息裁剪**：单用户消息上限 300 条，自动裁剪旧消息
- **TTL 清理**：超过 24 小时未活跃的对话自动清理

### SSE 流式输出优化

- **即时 start 事件**：Agent 路径的 SSE 端点立即发送 `start` 事件
- **心跳保活机制**：Agent 执行期间每秒发送 SSE 心跳注释
- **超时保护**：Agent 执行超过 120 秒时自动返回超时错误
- **前端等待提示**：Agent 处理中显示 `正在等待 {Agent名称} 响应...` 动态提示

---

## 历史对话管理

系统通过 MySQL 数据库实现完整的对话历史持久化与管理功能。

### 数据模型

- **conversations 表**：存储对话元数据（标题、创建时间、更新时间、所属用户）
- **conversation_messages 表**：存储对话消息（角色、内容、创建时间），通过外键关联对话
- 支持消息裁剪：单对话最多保留 200 条消息

### 消息完整性保障

- 用户消息和 AI 回复均通过 `_append_to_conversation` 函数同步保存到数据库
- 当 AI 响应异常为空时，自动保存占位消息 `"[系统提示] 响应生成失败，请稍后重试。"`，确保对话记录完整性
- 前端 `switchConversation` 加载消息时进行完整性校验（统计 user/assistant 消息数量），异常时输出警告日志

### 前端交互

- 侧边栏展示对话列表（标题、更新时间、消息数）
- 支持新建对话、切换对话、删除对话、重命名对话
- 新建对话自动创建空对话，发送消息后自动关联
- 切换对话时通过 API 加载完整消息历史，支持用户消息与 AI 回复的完整展示

---

## 安全措施

- API 错误消息去敏化（28 个端点均返回安全泛化消息）
- XSS 防护（HTML/CSS/JS 前端内置 HTML 转义）
- CSRF 防护（Origin/Referer 精确域名白名单校验）
- 认证暴力破解防护（登录/注册独立频率限制：10 次/5 分钟）
- API 全局限流（100 次/60 秒）
- 安全响应头注入（X-Content-Type-Options / X-Frame-Options / HSTS）
- 反序列化安全（checkpoint 持久化使用 JSON 格式）
- MySQL 参数化查询 / Cypher 注入白名单
- PBKDF2 密码哈希（100K 迭代）+ 常量时间比较
- JWT Token 认证 + 过期管理
- CORS 精确白名单
- 无硬编码密钥（全部通过环境变量注入）

---

## 依赖项

### 后端核心依赖

| 包 | 版本 | 用途 |
|---|------|------|
| `langgraph` | >=1.2.0 | Agent 编排框架 |
| `langgraph-checkpoint` | >=4.1.0 | 断点续聊检查点 |
| `langgraph-prebuilt` | >=1.1.0 | 预构建 Agent 组件 |
| `langchain-core` | >=1.4.0 | LangChain 核心库 |
| `langchain-openai` | >=1.2.0 | OpenAI 集成 |
| `langsmith` | >=0.8.0 | LLM 调试与追踪 |
| `openai` | >=2.32.0 | LLM API 客户端 |
| `tiktoken` | >=0.13.0 | Token 计数 |
| `dashscope` | >=1.20.0 | 百炼 Embedding |
| `qdrant-client` | >=1.16.0 | 向量数据库客户端 |
| `neo4j` | >=5.0.0 | 图数据库（可选） |
| `numpy` | >=2.0.0 | 数值计算 |
| `mysql-connector-python` | >=9.0.0 | MySQL 数据库驱动 |
| `fastapi` | >=0.136.0 | Web API 框架 |
| `uvicorn` | >=0.47.0 | ASGI 服务器 |
| `pydantic` | >=2.13.0 | 数据验证 |
| `pydantic-settings` | >=2.0.0 | 环境变量管理 |
| `python-dotenv` | >=1.2.0 | .env 文件加载 |
| `beautifulsoup4` | >=4.14.0 | HTML 解析（Web 搜索） |
| `requests` | >=2.33.0 | HTTP 客户端 |
| `PyPDF2` | >=3.0.0 | PDF 文件解析 |
| `python-docx` | >=1.1.0 | Word 文档生成与读取 |
| `pytest` | >=8.0.0 | 测试框架 |
| `pytest-asyncio` | >=1.0.0 | 异步测试支持 |
| `pytest-cov` | >=5.0.0 | 测试覆盖率 |

### 前端开发依赖

| 包 | 版本 | 用途 |
|------|------|------|
| `vitest` | ^3.0.0 | 测试框架 |
| `jsdom` | ^26.0.0 | DOM 模拟环境 |

完整依赖列表见 [requirements.txt](requirements.txt) 和 [frontend/package.json](frontend/package.json)。

---

## 贡献流程

本项目欢迎社区贡献。请遵循以下流程参与开发：

### 分支策略

- **main**：主分支，保持稳定可发布状态
- **develop**：开发分支，集成最新功能
- **feature/xxx**：功能分支，从 develop 创建
- **fix/xxx**：修复分支，从 develop 或 main 创建
- **release/xxx**：发布分支，从 develop 创建

### 提交规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型（type）：
- `feat`：新功能
- `fix`：Bug 修复
- `docs`：文档更新
- `style`：代码格式（不影响代码运行的变动）
- `refactor`：重构
- `test`：测试相关
- `chore`：构建过程或辅助工具的变动

### Pull Request 流程

1. Fork 本仓库
2. 从 `develop` 分支创建功能分支
3. 编写代码并确保通过所有测试
4. 提交 PR 到 `develop` 分支
5. 描述变更内容与原因
6. 等待代码审查与合并

详细的团队协作规范请参考 [git开发手册.md](git开发手册.md)。

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件（如有）。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [PRODUCT.md](PRODUCT.md) | 产品定位、目标用户画像、品牌人格、设计原则 |
| [DESIGN.md](DESIGN.md) | 设计系统规范：色彩/字体/圆角/间距/组件/动效 |
| [开发流程.md](开发流程.md) | 项目开发流程、分阶段实施计划、架构设计决策 |
| [git开发手册.md](git开发手册.md) | Git 团队协作规范：分支策略/提交规范/PR 流程 |
| [.env.example](.env.example) | 完整环境变量配置模板（40+ 配置项） |
| [PRD 文档](.trae/documents/PRD.md) | 产品需求文档：功能模块、页面设计、核心流程 |
| [技术架构](.trae/documents/TECHNICAL_ARCHITECTURE.md) | 技术架构文档：前后端架构、数据模型、API 设计 |
| [部署指南](.trae/documents/DEPLOYMENT_GUIDE.md) | 前端静态部署与 Nginx 配置 |
| [组件文档](.trae/documents/COMPONENT_DOCUMENTATION.md) | 前端模块 API 参考与架构说明 |
| [测试报告](.trae/documents/TEST_REPORT.md) | 前端 66 个测试用例完整报告 |
| [使用手册](.trae/documents/USER_MANUAL.md) | 用户操作指南：快速入门、界面介绍、功能使用 |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger API 交互文档（需启动服务） |

---

## 代码仓库文件清单

以下为需上传至代码仓库的完整文件与目录列表，所有冗余文件（编译产物、依赖包、IDE 配置、运行时数据）已排除。

### 根目录文件

| 文件 | 说明 | 处理规范 |
|------|------|---------|
| `.env.example` | 环境变量模板（40+ 配置项） | 不含真实密钥，可安全提交 |
| `.gitignore` | Git 忽略规则 | 已配置 Python/Node/IDE/Data/环境变量 排除 |
| `Dockerfile` | 多阶段 Docker 构建（Python 3.11） | 生产构建，含非 root 用户 + 健康检查 |
| `docker-compose.yml` | 服务编排（API + Qdrant + Neo4j） | Neo4j 使用 `full` profile 按需启动 |
| `README.md` | 项目主文档 | 本文件 |
| `PRODUCT.md` | 产品定位与品牌人格 | 静态文档 |
| `DESIGN.md` | 设计系统规范 | 静态文档 |
| `开发流程.md` | 开发流程与架构设计决策 | 中文文档 |
| `git开发手册.md` | Git 团队协作规范 | 中文文档 |
| `requirements.txt` | Python 依赖清单 | 含版本下限，按类别分组 |
| `test_upload.py` | 文件上传测试脚本（7 场景） | 开发工具，需服务器运行 |
| `check_messages.py` | 数据库消息诊断脚本 | 运维工具，需 MySQL 连接 |
| `fix_broken_conversation.py` | 修复不完整对话记录 | 运维工具，需 MySQL 连接 |

### 后端源码 (`src/`)

| 路径 | 说明 | 处理规范 |
|------|------|---------|
| `src/__init__.py` | 包初始化 | - |
| `src/config.py` | 全局配置（基于 pydantic-settings） | 含 40+ 环境变量，无硬编码密钥 |
| `src/llm.py` | LLM 统一调用层 | 多 Provider 支持 + 流式/非流式 |
| `src/embedding.py` | 向量嵌入层 | 云端 + 本地双模式 + 批量缓存 |
| `src/api/__init__.py` | API 包初始化 | - |
| `src/api/main.py` | FastAPI 服务（28 端点 + SSE + 中间件） | 最大文件，含全部 5 层中间件 |
| `src/agents/__init__.py` | Agent 模块初始化 | - |
| `src/agents/base_agent.py` | Agent 基类 | - |
| `src/agents/assistant.py` | Supervisor 总控 Agent | 关键词 + LLM 语义路由 |
| `src/agents/planner.py` | 学习规划师 | Plan-and-Solve |
| `src/agents/expert.py` | 学习专家 | ReAct + WebSearch |
| `src/agents/partner.py` | 学习伙伴 | RAG + FocusTimer |
| `src/agents/quizzer.py` | 出题助手 | QuizGen + RL |
| `src/agents/reviewer.py` | 错题分析师 | Reflection |
| `src/agents/examiner.py` | 备考顾问 | Plan-and-Solve |
| `src/core/__init__.py` | Core 包初始化 | - |
| `src/core/state.py` | 全局状态定义 | AgentState / UserProfile |
| `src/core/memory.py` | 向量存储 | Qdrant 本地/远程双模式 |
| `src/core/retriever.py` | 检索层 | RAG 混合检索 |
| `src/core/graph.py` | 知识图谱 | Neo4j + Cypher 注入防护 |
| `src/core/communication.py` | Agent 间通信 | 消息路由与聚合 |
| `src/core/checkpoint.py` | 对话存档 | JSON 持久化 + 自动恢复 |
| `src/core/user_store.py` | 用户管理 | MySQL 连接池 + 对话历史 CRUD + PBKDF2 密码哈希 |
| `src/core/file_processor.py` | 文件处理 | 上传/解析/存储，支持 PDF/Word/TXT/代码 |
| `src/core/word_generator.py` | Word 文档生成器 | 问答导出 + 文件问答下载 |
| `src/core/tools/__init__.py` | 工具包初始化 | - |
| `src/core/tools/base.py` | 工具基类 + ToolRegistry | 注册中心 |
| `src/core/tools/search.py` | Web 搜索工具 | SerpAPI / DuckDuckGo |
| `src/core/tools/timer.py` | 专注计时器 | - |
| `src/core/tools/document.py` | 文档生成器 | Word 文档 |
| `src/core/tools/quiz.py` | 出题引擎 + 能力评估 | - |

### 前端源码 (`frontend/`)

| 路径 | 说明 | 处理规范 |
|------|------|---------|
| `frontend/index.html` | SPA 主入口 | 纯 HTML，含无障碍 ARIA 标签 + 聊天页顶栏导航 |
| `frontend/guide.html` | 使用指南页面 | 含功能概述/快速上手/操作指南/FAQ/注意事项，响应式设计 |
| `frontend/package.json` | 前端依赖管理 | 仅含 vitest + jsdom（测试用） |
| `frontend/vitest.config.js` | 前端测试配置 | - |
| `frontend/css/variables.css` | CSS 自定义属性 | 色彩/字体/间距/圆角 |
| `frontend/css/base.css` | 全局重置与基础样式 | - |
| `frontend/css/layout.css` | 页面布局 | 栅格 + Flex + 聊天页顶栏 |
| `frontend/css/auth.css` | 登录/注册卡片 | - |
| `frontend/css/chat.css` | 聊天消息与输入区域 | 含文件上传进度条样式 |
| `frontend/css/sidebar.css` | 侧边栏组件 | - |
| `frontend/css/guide.css` | 指南页面样式 | 响应式（4断点）+ 暗色模式 + 动画 + 打印样式 |
| `frontend/css/responsive.css` | 响应式适配 + 暗色模式 | 含顶栏移动端适配 |
| `frontend/js/state.js` | 全局状态管理 | localStorage + sessionStorage |
| `frontend/js/utils.js` | 工具函数 | DOM 操作/表单校验/防抖/HTML 转义 |
| `frontend/js/api.js` | API 客户端 | 统一封装 REST 调用 + XHR 文件上传 |
| `frontend/js/sse.js` | SSE 流式请求 | fetch + ReadableStream |
| `frontend/js/toast.js` | 消息提示 | info/success/error/warning |
| `frontend/js/theme.js` | 主题切换 | 明暗模式 + 系统偏好跟随 |
| `frontend/js/auth.js` | 认证模块 | 登录/注册/退出/密码修改 |
| `frontend/js/conversations.js` | 对话管理 | 创建/切换/删除/重命名/列表加载 |
| `frontend/js/chat.js` | 聊天交互 | 消息渲染/SSE 流式/文件上传/进度显示/Markdown 解析 |
| `frontend/js/sidebar.js` | 侧边栏模块 | 用户信息/设置/Agent 选择/快捷操作 |
| `frontend/js/app.js` | 应用入口 | 路由管理/初始化 |
| `frontend/tests/setup.js` | 前端测试环境初始化 | DOM Mock |
| `frontend/tests/state.test.js` | 状态管理测试 | 15 用例 |
| `frontend/tests/utils.test.js` | 工具函数测试 | 16 用例 |
| `frontend/tests/api.test.js` | API 客户端测试 | 4 用例 |
| `frontend/tests/sse.test.js` | SSE 解析测试 | 6 用例 |
| `frontend/tests/toast.test.js` | 消息提示测试 | 7 用例 |
| `frontend/tests/auth.test.js` | 认证模块测试 | 3 用例 |
| `frontend/tests/chat.test.js` | 聊天模块测试 | 5 用例 |
| `frontend/tests/sidebar.test.js` | 侧边栏测试 | 10 用例 |

### 后端测试 (`tests/`)

| 路径 | 说明 | 处理规范 |
|------|------|---------|
| `tests/__init__.py` | 测试包初始化 | - |
| `tests/conftest.py` | 全局测试夹具 | Fixtures |
| `tests/test_core.py` | 基础设施测试 | Config/LLM/Embedding/Tools |
| `tests/test_agents.py` | Agent 模块测试 | 7 个 Agent 初始化与调用 |
| `tests/test_coverage_boost.py` | 覆盖率补充测试 | - |
| `tests/test_e2e.py` | 端到端测试 | 完整学习流程 |
| `tests/test_context_aware.py` | 上下文感知测试 | - |
| `tests/test_phase5.py` | Phase 5 安全加固测试 | - |

### 项目文档 (`.trae/documents/`)

| 路径 | 说明 | 处理规范 |
|------|------|---------|
| `.trae/documents/PRD.md` | 产品需求文档 | 位于 IDE 目录，属项目文档 |
| `.trae/documents/TECHNICAL_ARCHITECTURE.md` | 技术架构文档 | 位于 IDE 目录，属项目文档 |
| `.trae/documents/DEPLOYMENT_GUIDE.md` | 部署指南 | 位于 IDE 目录，属项目文档 |
| `.trae/documents/COMPONENT_DOCUMENTATION.md` | 前端组件文档 | 位于 IDE 目录，属项目文档 |
| `.trae/documents/TEST_REPORT.md` | 测试报告 | 位于 IDE 目录，属项目文档 |
| `.trae/documents/USER_MANUAL.md` | 用户使用手册 | 位于 IDE 目录，属项目文档 |

### 排除清单（以下文件/目录不提交至仓库）

| 路径 | 排除原因 | 对应 .gitignore 规则 |
|------|---------|---------------------|
| `.env` / `*.env` | 含真实密钥，安全风险 | `*.env` |
| `data/` | 运行时数据（上传文件/输出文档/向量库/存档） | `data/*.json` + `data/qdrant_store/` + `data/checkpoints/` |
| `__pycache__/` | Python 编译缓存 | `__pycache__/` + `*.pyc` |
| `node_modules/` | 前端依赖，可通过 `npm install` 恢复 | `node_modules/` |
| `package-lock.json` | 自动生成的锁文件 | `package-lock.json` |
| `.pytest_cache/` | 测试缓存 | `.pytest_cache/` |
| `.coverage` / `htmlcov/` | 覆盖率报告 | `.coverage` + `htmlcov/` |
| `.vscode/` / `.idea/` | IDE 个人配置 | `.vscode/` + `.idea/` |
| `models/` | 本地模型文件（体积大） | `models/` |
| `venv/` / `env/` | Python 虚拟环境 | `venv/` + `env/` |
| `*.log` / `logs/` | 日志文件 | `*.log` + `logs/` |
| `build/` / `dist/` / `*.egg-info/` | Python 构建产物 | `build/` + `dist/` + `*.egg-info/` |
| `.DS_Store` / `Thumbs.db` | 操作系统临时文件 | `.DS_Store` + `Thumbs.db` |