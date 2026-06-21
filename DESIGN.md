---
name: 学习辅助系统
description: AI 驱动的个性化长期学习追踪系统，多智能体协作完成学习全链路闭环。
colors:
  matte-indigo: "#4a5a7f"
  matte-indigo-hover: "#5d6e99"
  matte-indigo-subtle: "#e8ecf3"
  warm-page: "#f8f7f5"
  warm-surface: "#f2f1ee"
  warm-border: "#e2e0db"
  warm-text-primary: "#2d2c2a"
  warm-text-secondary: "#6e6c68"
typography:
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.matte-indigo}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "10px 24px"
  button-primary-hover:
    backgroundColor: "{colors.matte-indigo-hover}"
  card-login:
    backgroundColor: "linear-gradient(135deg, {colors.warm-surface}, {colors.warm-page})"
    rounded: "{rounded.lg}"
    padding: "{spacing.xl}"
---

# Design System: 学习辅助系统

## 1. Overview

**Creative North Star: "The Thoughtful Tutor"**

一个克制、温暖、值得信赖的学习工具界面。像一位思虑周全的导师——不多言，但每一句话都经过斟酌；不炫技，但每一个交互都让你感到被理解。它记得你的薄弱点，安静地准备好下一步，在你需要时出现，在不需要时退到视野边缘。

视觉上，系统采用极简中性基调：暖灰白的底色为长时间阅读提供舒适的视觉环境，哑光靛蓝作为唯一的强调色出现在按钮、链接和关键状态指示中，占用约 10% 的交互面。色彩的稀缺性本身就是一种态度——这不是一个需要"吸引眼球"的产品，而是一个你愿意长时间停留的地方。

界面元素使用柔和的圆角（8-12px）和微妙渐变背景，hover 时温和响应而非突变。动画极简、可全局关闭，一切服务于学习专注度而非视觉刺激。

**Key Characteristics:**
- 极简暖灰白基调，单色低饱和靛蓝强调
- 柔和圆角（8-12px），无尖锐直角
- 动画克制，默认关闭过渡动效
- 不依赖色彩传达信息，图标和文字辅助区分状态
- 长时间阅读友好，视觉疲劳度低

## 2. Colors

暖灰白为基底的极简中性调色板。单一低饱和强调色——哑光靛蓝——承载所有交互语义，不超过任何屏幕 10% 的色域占比。

### Primary
- **Matte Indigo** (`#4a5a7f`): 按钮背景、链接文字、选中状态指示器。唯一的强调色，用于所有需要用户注意的交互元素。
- **Matte Indigo Hover** (`#5d6e99`): hover 状态，比主色提亮 10%。
- **Matte Indigo Subtle** (`#e8ecf3`): 极淡的靛蓝底色，用于选中行高亮、消息气泡中我的发言。

### Neutral
- **Warm Page** (`#f8f7f5`): 页面底色，略带暖意的近白色，降低长时间阅读的视觉疲劳。
- **Warm Surface** (`#f2f1ee`): 卡片、容器、输入框背景。比页面底色稍深，形成微妙的层次。
- **Warm Border** (`#e2e0db`): 分割线、边框。足够可见但不过度强调。
- **Warm Text Primary** (`#2d2c2a`): 正文颜色，深暖灰代替纯黑。
- **Warm Text Secondary** (`#6e6c68`): 辅助文字、占位符、说明文字。

### Named Rules
**The 10% Rule.** 哑光靛蓝在任何屏幕上的色域占比不超过 10%。它出现的地方就是行动点——按钮、选中态、链接——其余区域全部归暖灰白。强调色的稀缺是让界面保持安静的核心手段。

**The No-Pure-Black Rule.** 禁止使用 `#000` 和 `#fff`。正文使用暖灰黑 `#2d2c2a`，底色使用暖灰白 `#f8f7f5`，所有中性色向暖色方向偏移。

## 3. Typography

**Font Stack:** System UI — `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`

**Character:** 不引入自定义字体，完全依赖系统原生字体栈。这减少了网络请求和 FOUT 风险，同时让界面在不同操作系统上呈现最自然的阅读体验。这不是一个需要"品牌字体识别"的产品——阅读舒适度优先于视觉独特性。

### Hierarchy
- **Title** (600, 1.25rem, 1.3): 页面标题、卡片标题、侧边栏分区标题。权重足以区分层级，但不夸张。
- **Body** (400, 1rem, 1.6): 聊天消息正文、设置项标签、表单文案。行高 1.6 为长时间阅读提供舒适的呼吸感。最大行宽 65-75ch。
- **Label** (500, 0.875rem, 1.4): 输入框标签、状态标签、辅助信息。半粗体建立与正文的层次差异。

## 4. Elevation

系统采用平坦策略。没有物理阴影，层次通过背景色差异传达——页面底色 (`warm-page`) 与卡片底色 (`warm-surface`) 之间的微妙对比足以区分层级。唯一的例外是登录卡片，使用轻阴影 (`0 4px 24px rgba(0,0,0,0.08)`) 在页面上创造微弱的浮起感，暗示其作为入口的仪式感。

**The Flat-By-Default Rule.** 所有界面默认平坦。阴影仅用于登录卡片入口，其他地方禁止。如果内容需要分层，优先使用背景色差或 1px 暖灰边框。

## 5. Components

### Buttons
- **Shape:** 柔和圆角 (`10px`)，无尖锐矩形。
- **Primary:** 哑光靛蓝背景 (`#4a5a7f`)，白色文字，内边距 `10px 24px`。文字前缀 emoji 图标（如 🔑 📝 💾）作为视觉速记。
- **Hover:** 背景提亮至 `#5d6e99`，100ms ease-in-out 过渡（在动效开关未关闭时）。
- **Secondary / Text:** Streamlit 默认呈现，不做自定义覆盖。保持框架一致性。

### Cards
- **Login Card:** 唯一的自定义卡片。12px 圆角，从 `warm-surface` 到 `warm-page` 的 135° 对角线渐变。`32px` 内边距，宽度上限 420px。轻阴影 (`0 4px 24px rgba(0,0,0,0.08)`) 营造入口的仪式感。
- **其他卡片:** 不使用。对话区域采用 Streamlit 原生 `st.chat_message` 组件。

### Inputs
- **Style:** Streamlit 默认输入框，自动继承系统字体与暖灰白背景。不自定义输入框外观，保持框架原生的可访问性处理。
- **Focus:** 浏览器默认焦点环（不覆盖），保证键盘导航可发现性。

### Navigation
- **Sidebar:** Streamlit 原生侧边栏。分区使用 `st.sidebar.expander` 折叠面板，顶部用户信息区域用 1px `warm-border` 分割线区分。
- **Agent Selector:** 单选框形式，7 个选项 + 自动识别。展开状态默认可见。

### Status Indicators
- **Error:** 红色错误框，前缀 ❌ emoji + 文字。不使用边框左侧色条（违反 side-stripe 禁令），改用完整背景色块。
- **Success:** 绿色成功框，前缀 ✅ emoji + 文字。
- **Warning:** 黄色警告框，前缀 ⚠️ emoji + 文字。
- **Loading:** Streamlit `st.spinner` 组件，显示在操作区域原地。

## 6. Do's and Don'ts

### Do:
- **Do** 使用暖灰白底色 (`#f8f7f5`) 替代纯白，降低长时间阅读疲劳。
- **Do** 哑光靛蓝 (`#4a5a7f`) 作为唯一强调色，限定在 ≤10% 的交互面。
- **Do** 所有状态提示同时使用图标和文字，不单靠颜色区分。
- **Do** 保持柔和圆角 (8-12px)，拒绝尖锐直角带来攻击感。
- **Do** 动画默认关闭，提供全局开关让用户自主启用。

### Don't:
- **Don't** 做成纯题库类刷题工具——无讲解、无规划、无复盘的单一题海模式。
- **Don't** 引入游戏化闯关、花哨动效、弹窗激励——保持严肃自主学习工具的界面氛围。
- **Don't** 采用直播网校式的重营销导流、课程售卖界面模式——聚焦 AI 辅助学习本身。
- **Don't** 使用 `border-left` 或 `border-right` 大于 1px 的彩色侧边条。
- **Don't** 使用 `#000` 纯黑或 `#fff` 纯白——所有中性色向暖色调偏移。