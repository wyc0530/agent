# 学习辅助系统 — 前端重构部署指南

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Web 服务器 | Nginx / Apache / Caddy / 任意 HTTP 服务器 |
| 后端服务 | Python 3.10+ (FastAPI) |
| 浏览器 | Chrome 120+, Firefox 120+, Safari 17+, Edge 120+ |
| Node.js | 18+ (仅开发/测试需要) |

## 2. 快速部署

### 2.1 静态文件部署

`frontend/` 目录下所有文件为纯静态资源，可直接部署到任意 Web 服务器。

```bash
# 方式一：使用 Python 内置 HTTP 服务器（开发/测试）
cd frontend/
python -m http.server 3000

# 方式二：使用 Nginx
cp -r frontend/* /var/www/html/

# 方式三：使用 Docker + Nginx
docker run -d -p 80:80 \
  -v $(pwd)/frontend:/usr/share/nginx/html:ro \
  nginx:alpine
```

### 2.2 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html/frontend;
    index index.html;

    # SPA 路由：所有路由指向 index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location ~* \.(css|js|png|jpg|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
```

### 2.3 后端启动

```bash
# 确保后端 FastAPI 服务运行
cd agent/
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## 3. 配置说明

### 3.1 API 地址配置

前端默认连接 `http://localhost:8000`。如需修改，编辑 `frontend/js/api.js`：

```javascript
var API_BASE = 'http://your-api-host:8000';
```

或通过环境变量注入（Nginx 配置中使用 `sub_filter` 替换）。

### 3.2 超时配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| TIMEOUT_DEFAULT | 10000ms | 普通 API 请求超时 |
| TIMEOUT_STREAM | 120000ms | SSE 流式请求超时 |

可在 `frontend/js/api.js` 中修改。

## 4. 目录结构

```
frontend/
├── index.html              # 主入口，SPA 单页面
├── package.json            # 开发依赖（测试用）
├── vitest.config.js        # 测试配置
├── css/
│   ├── variables.css       # CSS 自定义属性
│   ├── base.css            # 全局重置与基础样式
│   ├── layout.css          # 页面布局
│   ├── auth.css            # 登录/注册卡片
│   ├── chat.css            # 聊天消息与输入
│   ├── sidebar.css         # 侧边栏组件
│   └── responsive.css      # 响应式与暗色模式
├── js/
│   ├── state.js            # 全局状态管理
│   ├── utils.js            # 工具函数
│   ├── api.js              # API 客户端
│   ├── sse.js              # SSE 流式请求
│   ├── toast.js            # 消息提示
│   ├── auth.js             # 认证模块
│   ├── chat.js             # 聊天交互
│   ├── sidebar.js          # 侧边栏模块
│   └── app.js              # 应用入口
└── tests/
    ├── setup.js            # 测试环境初始化
    ├── state.test.js       # 状态管理测试
    ├── utils.test.js       # 工具函数测试
    ├── api.test.js         # API 客户端测试
    ├── sse.test.js         # SSE 解析测试
    ├── toast.test.js       # 提示消息测试
    ├── auth.test.js        # 认证模块测试
    ├── chat.test.js        # 聊天模块测试
    └── sidebar.test.js     # 侧边栏测试
```

## 5. Docker 部署

### 5.1 前端 Dockerfile

```dockerfile
FROM nginx:alpine
COPY frontend/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 5.2 docker-compose.yml

```yaml
version: '3.8'
services:
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - API_BASE=http://localhost:8000
```

## 6. 性能优化

- 所有 CSS/JS 文件均为静态资源，支持浏览器缓存
- `marked.js` 通过 CDN 加载，约 20KB gzipped
- 聊天消息历史限制 50 条，防止内存溢出
- 流式输出使用 `textContent` 避免 innerHTML 开销
- 可选的代码压缩：部署前使用 `terser` 压缩 JS，`csso` 压缩 CSS

## 7. 安全建议

- 生产环境使用 HTTPS
- 配置 CSP (Content-Security-Policy) 头
- 禁止直接访问 `.js` 源文件（仅允许压缩后的 bundle）
- Token 存储在 localStorage，注意 XSS 风险
- 定期更新 CDN 依赖（`marked.js`）