# 学习辅助系统 — 组件文档

## 1. 架构概览

```
┌─────────────────────────────────────────────────┐
│                    index.html                     │
│  ┌──────────┐  ┌──────────────────────────────┐  │
│  │  Sidebar  │  │         ChatArea              │  │
│  │  ┌──────┐ │  │  ┌────────────────────────┐  │  │
│  │  │User  │ │  │  │     MessageList         │  │  │
│  │  │Info  │ │  │  │  ┌──────────────────┐  │  │  │
│  │  └──────┘ │  │  │  │  MessageBubble[] │  │  │  │
│  │  ┌──────┐ │  │  │  └──────────────────┘  │  │  │
│  │  │Settings│ │  │  └────────────────────────┘  │  │
│  │  └──────┘ │  │  ┌────────────────────────┐  │  │
│  │  ┌──────┐ │  │  │     ChatInput           │  │  │
│  │  │Password│ │  │  └────────────────────────┘  │  │
│  │  └──────┘ │  └──────────────────────────────┘  │
│  │  ┌──────┐ │                                      │
│  │  │Agent │ │          ┌──────────┐               │
│  │  │Select│ │          │  Toast   │               │
│  │  └──────┘ │          └──────────┘               │
│  │  ┌──────┐ │                                      │
│  │  │Quick │ │                                      │
│  │  │Actions│ │                                      │
│  │  └──────┘ │                                      │
│  │  ┌──────┐ │                                      │
│  │  │Quiz  │ │                                      │
│  │  └──────┘ │                                      │
│  └──────────┘                                      │
└─────────────────────────────────────────────────┘
```

## 2. 模块依赖关系

```
app.js (入口)
├── state.js (无依赖)
├── utils.js (无依赖)
├── api.js → state.js
├── sse.js → api.js, utils.js
├── toast.js → utils.js
├── auth.js → api.js, utils.js, toast.js, app.js
├── chat.js → state.js, utils.js, api.js, sse.js, toast.js
└── sidebar.js → state.js, utils.js, api.js, auth.js, chat.js, toast.js
```

## 3. 模块详细说明

### 3.1 state.js — 全局状态管理

**职责**：管理应用全局状态，包括认证信息、消息历史、用户资料和 Agent 选择。

**存储策略**：

| 数据 | 存储位置 | Key |
|------|---------|-----|
| Token | localStorage | `ls_token` |
| user_id | localStorage | `ls_user_id` |
| username | localStorage | `ls_username` |
| display_name | localStorage | `ls_display_name` |
| 消息历史 | sessionStorage | `ss_messages` |
| 用户资料 | sessionStorage | `ss_profile` |
| 当前 Agent | sessionStorage | `ss_current_agent` |

**API 参考**：

```javascript
// 认证状态
AppState.isLoggedIn()           // → boolean
AppState.getToken()             // → string
AppState.setToken(token)        // → void
AppState.getUserId()            // → string
AppState.setUserId(id)          // → void
AppState.getUsername()          // → string
AppState.setUsername(name)      // → void
AppState.getDisplayName()       // → string
AppState.setDisplayName(name)   // → void
AppState.applyLogin(authData)   // 批量设置登录状态 → void

// 消息管理
AppState.getMessages()          // → Message[]
AppState.setMessages(messages)  // → void
AppState.addMessage(msg)        // 追加消息（自动截断 >50）→ Message[]

// 用户资料
AppState.getProfile()           // → Profile
AppState.setProfile(profile)    // → void

// Agent 选择
AppState.getCurrentAgent()      // → string
AppState.setCurrentAgent(agent) // → void

// 退出登录
AppState.clearAll()             // 清除所有状态 → void
```

**数据模型**：

```typescript
interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  avatar: string;
  agent?: string;
  timestamp: number;
}

interface Profile {
  display_name: string;
  email: string;
  level: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  target_field: string;
  available_time: number;
  preference: 'comprehensive' | 'visual' | 'auditory' | 'reading' | 'practice';
}
```

### 3.2 utils.js — 工具函数

**职责**：提供通用工具函数，包括 DOM 操作、表单校验、格式化、防抖节流等。

**API 参考**：

```javascript
// DOM 操作
Utils.$(selector, parent?)     // → Element | null (querySelector)
Utils.$$(selector, parent?)    // → NodeList (querySelectorAll)
Utils.createEl(tag, attrs?, children?) // → Element

// 表单校验
Utils.validateRequired(value, fieldName)  // → string | null
Utils.validateMinLength(value, min, fieldName) // → string | null
Utils.validateEmail(value)                // → string | null

// 安全处理
Utils.escapeHtml(str)          // → string (防 XSS)
Utils.safeJsonParse(str, fallback?) // → any

// 工具函数
Utils.debounce(fn, delay)      // → Function
Utils.throttle(fn, limit)      // → Function
Utils.formatTime(timestamp)    // → string (HH:MM)
Utils.scrollToBottom(el)       // → void
```

**createEl 属性映射**：

| 属性名 | 处理方式 |
|--------|---------|
| `className` | `el.className = value` |
| `textContent` | `el.textContent = value` |
| `innerHTML` | `el.innerHTML = value` |
| `on*` 前缀 | `el.addEventListener(event, value)` |
| `style` (对象) | `Object.assign(el.style, value)` |
| 其他 | `el.setAttribute(key, value)` |

### 3.3 api.js — API 客户端

**职责**：封装所有后端 REST API 调用，处理认证、超时和错误。

**配置**：

```javascript
ApiClient.setBaseUrl('http://localhost:8000');
```

**API 参考**：

```javascript
// 认证
ApiClient.login(username, password)           // → Promise<LoginResponse>
ApiClient.register(username, password, displayName?, email?) // → Promise<LoginResponse>
ApiClient.logout()                             // → Promise<void>

// 用户
ApiClient.getProfile()                         // → Promise<Profile>
ApiClient.updateProfile(profileData)           // → Promise<Profile>
ApiClient.changePassword(oldPassword, newPassword) // → Promise<void>

// 健康检查
ApiClient.checkHealth()                        // → Promise<Response>

// 流式对话
ApiClient.streamChatRequest(payload)           // → Promise<Response> (原始 Response)

// 错误类型
ApiClient.ApiError                             // 构造函数
// new ApiClient.ApiError(message, statusCode)
```

**请求头构建**：

- 自动附加 `Content-Type: application/json`
- 如果存在 Token，附加 `Authorization: Bearer {token}`
- 使用 `AbortController` 实现超时控制

### 3.4 sse.js — SSE 流式请求

**职责**：使用 `fetch()` + `ReadableStream` 实现 POST SSE，处理流式对话。

**API 参考**：

```javascript
// 解析 SSE 行
SSE.parseLine(line)  // → object | null

// 流式对话
SSE.streamChat(payload, callbacks)  // → Promise<void>
```

**回调函数**：

```javascript
SSE.streamChat(payload, {
  onStart: function(data) {
    // data.agent_role - 实际处理的 Agent
  },
  onChunk: function(chunk) {
    // chunk - 本次到达的文本片段
  },
  onDone: function() {
    // 流式传输完成
  },
  onError: function(error) {
    // error - 错误消息
  }
});
```

**SSE 事件类型**：

| type | 含义 | 数据字段 |
|------|------|---------|
| `start` | 流式开始 | `agent_role` |
| `chunk` | 文本片段 | `content` |
| `done` | 传输完成 | - |
| `error` | 错误 | `content` |

### 3.5 toast.js — 消息提示

**职责**：显示浮动提示消息，支持多种类型和自动消失。

**API 参考**：

```javascript
Toast.show(message, type?, duration?)
// message: string - 提示文本
// type: 'info' | 'success' | 'error' | 'warning' (默认 'info')
// duration: number - 显示时长(ms)，0 表示不自动消失 (默认 3000)
// 返回: Element - toast 元素
```

### 3.6 auth.js — 认证模块

**职责**：处理登录、注册、退出登录和密码修改的完整交互流程。

**API 参考**：

```javascript
// 初始化登录页面事件
Auth.initLoginPage()

// 处理登录/注册
Auth.handleLogin()
Auth.handleRegister()

// 退出登录
Auth.handleLogout()
Auth.showLogoutConfirm()  // 显示确认弹窗

// 修改密码
Auth.handlePasswordChange()
```

### 3.7 chat.js — 聊天模块

**职责**：处理聊天消息的渲染、发送、流式更新和交互。

**API 参考**：

```javascript
// 初始化聊天界面
Chat.initChat()

// 渲染历史消息
Chat.renderHistory()

// 发送消息
Chat.sendMessage()

// 快捷聊天（预设消息 + Agent）
Chat.triggerQuickChat(message, agentRole)

// Agent 角色标签
Chat.AGENT_ROLE_LABELS
// { auto: '自动识别', planner: '学习规划师', ... }
```

**消息渲染流程**：

```
用户输入 → 清空输入框 → 添加用户消息到 Store → 渲染用户消息气泡
→ 创建流式消息占位 → 显示"正在等待..." → 发起 SSE 请求
→ onChunk: 逐字更新内容（带光标动画）
→ onDone: 移除光标，保存到 Store
→ onError: 显示错误消息
```

### 3.8 sidebar.js — 侧边栏模块

**职责**：管理侧边栏所有交互，包括用户信息、设置、密码、Agent 选择、快捷操作和测验生成。

**API 参考**：

```javascript
// 初始化
Sidebar.init()

// 侧边栏控制
Sidebar.toggleSidebar()
Sidebar.closeSidebar()

// Agent 选择器同步
Sidebar.syncAgentSelector(agentRole)
```

### 3.9 app.js — 应用入口

**职责**：管理路由、应用初始化和全局事件。

**API 参考**：

```javascript
// 路由
App.router.navigate('login' | 'chat')
App.router.current()  // → string

// 初始化
App.init()
```

**路由规则**：

| Hash | 页面 | 条件 |
|------|------|------|
| `#login` | 登录/注册页 | 默认（未认证） |
| `#chat` | 聊天主界面 | 已认证后默认 |

## 4. CSS 样式架构

### 4.1 文件结构

| 文件 | 职责 |
|------|------|
| `variables.css` | CSS 自定义属性（颜色、字体、间距、阴影、圆角、过渡） |
| `base.css` | 全局重置、排版、按钮、表单、滚动条、无障碍 |
| `layout.css` | 页面布局（侧边栏、主内容区、登录页、聊天页） |
| `auth.css` | 登录/注册卡片、Tab 切换、表单 |
| `chat.css` | 消息气泡、空态、流式输出、输入区域、Markdown 内容 |
| `sidebar.css` | 用户信息、折叠面板、设置表单、Agent 选择器、快捷操作、测验、弹窗、Toast |
| `responsive.css` | 媒体查询（平板、手机、暗色模式、减少动画） |

### 4.2 设计系统

**色彩体系**：

| 变量 | 亮色值 | 暗色值 | 用途 |
|------|--------|--------|------|
| `--color-page` | `#f8f7f5` | `#1a1a18` | 页面背景 |
| `--color-surface` | `#f2f1ee` | `#252423` | 卡片/侧边栏背景 |
| `--color-border` | `#e2e0db` | `#3d3c39` | 边框 |
| `--color-text-primary` | `#2d2c2a` | `#e8e6e3` | 主文字 |
| `--color-text-secondary` | `#6e6c68` | `#9e9c98` | 次要文字 |
| `--color-accent` | `#4a5a7f` | `#7a8ab5` | 主色调 |
| `--color-accent-hover` | `#5d6e99` | `#8e9ec9` | hover 态 |

**间距系统**：基于 4px 基准，从 `--space-1`(4px) 到 `--space-12`(48px)。

**字体系统**：`--font-sans`（中文）和 `--font-mono`（代码），字号从 `--text-xs` 到 `--text-2xl`。

## 5. 事件流

### 5.1 登录流程

```
用户点击登录 → Auth.handleLogin()
  → 表单校验 → ApiClient.login()
  → 成功: AppState.applyLogin() → App.router.navigate('chat')
  → 失败: Toast.show(error)
  → 最终: 恢复按钮状态
```

### 5.2 聊天流程

```
用户输入消息 → Chat.sendMessage()
  → 清空输入框 → AppState.addMessage(userMsg)
  → 渲染用户消息 → 创建流式占位 → SSE.streamChat()
  → onChunk: 更新 DOM → onDone: finalizeMessage()
  → AppState.addMessage(assistantMsg)
```

### 5.3 设置保存流程

```
用户修改设置 → 点击保存 → Sidebar 收集表单数据
  → ApiClient.updateProfile() → AppState.setProfile()
  → 更新 display_name → Toast.show('已保存')
```

## 6. 浏览器兼容性

| 特性 | Chrome | Firefox | Safari | Edge |
|------|--------|---------|--------|------|
| CSS Variables | 120+ | 120+ | 17+ | 120+ |
| CSS Grid | 120+ | 120+ | 17+ | 120+ |
| fetch() | 120+ | 120+ | 17+ | 120+ |
| ReadableStream | 120+ | 120+ | 17+ | 120+ |
| AbortController | 120+ | 120+ | 17+ | 120+ |
| `<details>` | 120+ | 120+ | 17+ | 120+ |
| prefers-color-scheme | 120+ | 120+ | 17+ | 120+ |
| prefers-reduced-motion | 120+ | 120+ | 17+ | 120+ |