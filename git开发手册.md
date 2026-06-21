# Git 团队开发手册

## 0. 目标

本手册用于规范团队成员在项目开发中如何使用 Git，确保：

- 多人协作不冲突
- 代码可追溯
- 开发流程清晰稳定

***

## 1. 基本概念（必须理解）

### 1.1 仓库（Repository）

项目代码的整体存储位置。

***

### 1.2 分支（Branch）

每个人开发功能时使用的独立代码线。

- main：稳定版本（禁止直接开发）
- feature/\*：功能开发
- fix/\*：问题修复

***

### 1.3 提交（Commit）

一次代码修改记录。

***

### 1.4 远程仓库（Remote）

团队共享代码的位置（GitHub / GitLab）。

***

## 2. 初次使用（只做一次）

### 2.1 克隆项目

```bash
git clone <repo_url>
cd project
```

***

### 2.2 查看当前状态

```bash
git status
```

***

## 3. 日常开发流程（必须严格遵守）

这是团队开发的核心流程。

***

### Step 1：切换到主分支并更新代码

```bash
git checkout main
git pull origin main
```

作用：

- 获取最新代码
- 避免冲突

***

### Step 2：创建自己的功能分支

```bash
git checkout -b feature/你的功能名
```

示例：

```bash
git checkout -b feature/login-api
git checkout -b feature/todo-ui
```

***

### Step 3：编写代码

在自己的分支上开发。

***

### Step 4：提交代码

```bash
git add .
git commit -m "feat: 功能描述"
```

提交规范：

- feat: 新功能
- fix: 修复问题
- refactor: 重构
- docs: 文档

示例：

```bash
git commit -m "feat: add login API"
```

***

### Step 5：同步最新主分支（防止冲突）

```bash
git fetch origin
git merge origin/main
```

***

### Step 6：推送到远程

```bash
git push origin feature/你的功能名
```

***

### Step 7：发起合并请求（PR）

在 GitHub / GitLab：

1. 创建 Pull Request
2. 等待 review
3. 合并到 main

***

## 4. 团队协作规则（必须遵守）

### 4.1 禁止直接修改 main 分支

错误行为：

```bash
git checkout main
# 修改代码并提交
```

***

### 4.2 每个功能必须使用独立分支

正确：

```bash
feature/login
feature/todo
```

***

### 4.3 每天至少同步一次 main

```bash
git checkout main
git pull
```

***

### 4.4 提交要小且频繁

避免：

- 一次提交上千行代码
- 长时间不提交

***

### 4.5 合并必须通过 PR

原因：

- 可 review
- 可回滚
- 可记录变更

***

## 5. 冲突处理（重要）

当出现冲突时：

```bash
git merge origin/main
```

Git 会标记冲突文件：

```
<<<<<<< HEAD
你的代码
=======
别人代码
>>>>>>> main
```

处理方法：

1. 手动修改代码
2. 删除标记符号
3. 保留正确逻辑

完成后：

```bash
git add .
git commit
```

***

## 6. 常用命令速查表

### 查看状态

```bash
git status
```

***

### 查看分支

```bash
git branch
```

***

### 切换分支

```bash
git checkout 分支名
```

***

### 创建分支

```bash
git checkout -b 分支名
```

***

### 添加文件

```bash
git add .
```

***

### 提交

```bash
git commit -m "说明"
```

***

### 拉取更新

```bash
git pull
```

***

### 推送

```bash
git push
```

***

### 查看历史

```bash
git log --oneline
```

***

## 7. 项目协作建议

### 7.1 分工边界

- backend：只修改 backend/
- frontend：只修改 frontend/
- api\_client：统一接口调用

***

### 7.2 接口协作流程

1. 定义 API 文档（负责人）
2. frontend 使用 mock 数据开发(亮哥负责)
3. backend 实现接口
4. 前端接入真实 API

***

### 7.3 文件冲突避免

- 不修改不属于自己的模块
- 修改公共文件前先沟通

***

## 8. 常见错误

### 错误 1：忘记拉代码

后果：

- 大量冲突

***

### 错误 2：直接在 main 写代码

后果：

- 无法回滚
- 破坏稳定版本

***

### 错误 3：长期不合并

后果：

- 合并困难
- 冲突复杂

***

## 9. 最低执行标准（必须做到）

1. 每次开发前先 pull
2. 每个功能单独分支
3. 每天同步 main
4. 使用 PR 合并
5. 不直接改 main

***

## 10. 推荐进阶（后续可引入）

- Git commit 规范工具（commitlint）
- 自动化测试（CI）
- Docker 统一开发环境
- OpenAPI 文档生成

***

本手册为最小可行规范，严格执行即可支撑当前团队开发。\
如项目复杂度增加，再逐步引入更高级流程。
