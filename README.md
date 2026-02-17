# QQ 机器人 OpenAI 集成方案

基于 NapCat **反向 WebSocket** 的 QQ 机器人 AI 自动回复系统，配套现代化 Web 管理面板。

---

## 项目特性

- **AI 自动回复** — 支持私聊 / 群聊，群聊可配置仅 @时回复 或 @所有人也回复
- **多模型配置** — 聊天模型与视觉模型独立配置，灵活对接 OpenAI 兼容 API
- **图像识别** — 启用视觉模型后自动分析消息中的图片内容
- **表情转义** — 将用户发送的 QQ 表情 (`[CQ:face,id=...]`) 转换为文字描述供 AI 理解
- **上下文记忆** — 多轮对话历史 + 可选上下文压缩（摘要式淘汰旧轮次）
- **模拟打字** — 按阅读→思考→打字的自然节奏延迟回复，可调速度倍率
- **黑白名单** — 按用户 ID 或群组 ID 过滤，互斥模式（白名单优先）
- **好友验证** — HMAC Token 自动审批好友请求，配合公开 Token 生成页面
- **IP 安全** — 多维度安全规则（速率、连接、行为、模式）+ IP 封禁管理
- **密码认证** — bcrypt 密码哈希 + JWT HttpOnly Cookie 会话，首次启动自动生成
- **Web 管理面板** — Azure Portal 风格，Vue 3 + Element Plus，多选项卡配置

## 系统要求

- Python 3.10+
- NapCat 已运行并配置反向 WebSocket
- OpenAI 兼容 API 密钥

## 安装

```bash
# 克隆并进入项目
cd qq_with_openai

# (可选) 创建虚拟环境
python -m venv venv && source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 1. 启动服务

```bash
python -m backend.run
```

服务端口由 `config/default_config.json` 中 `advanced.service_port` 决定，默认 `5000`。
也可通过环境变量覆盖：

```bash
FLASK_PORT=8000 python -m backend.run
```

### 2. 首次登录

首次启动会在终端打印随机生成的管理员密码，请妥善保存。访问 `http://localhost:<端口>` 进入登录页面。

### 3. 配置 NapCat 连接

本项目作为 **WebSocket 服务端**，NapCat 作为客户端反向连接：

1. 在 NapCat 中配置反向 WebSocket 地址为 `ws://<本服务IP>:<端口>/ws/napcat`
2. 如设置了 Token，在 **高级设置** 中填写相同的 `napcat_token`
3. NapCat 连接后，面板概览页会显示连接状态

### 4. 配置 AI 模型

在 **聊天模型** 选项卡中填写：

- **Base URL** — OpenAI 兼容 API 地址
- **API Key** — 密钥
- **Model** — 模型名称
- 可点击 **测试连接** 验证

如需图像识别，在 **视觉模型** 选项卡中启用并配置。

### 5. 自定义设置

在 **自定义设置** 选项卡中配置：

- **System Prompt** — AI 的角色设定与行为逻辑
- **自动回复** / **群聊仅@时回复** / **@所有人时也回复**
- **表情转义** — 将 QQ 表情 CQ 码转为文字（如 `[CQ:face,id=14]` → `[微笑]`）供 AI 理解
- **模拟人工打字** — 启用后按真实人类节奏延迟回复
- **上下文记忆** — 回溯条数、压缩开关、单条建议长度等

### 6. 好友验证

访问 `http://<服务地址>/token` 进入公开 Token 生成页面，输入 QQ 号获取验证令牌，将令牌作为好友验证消息发送即可自动通过。

Token 有效期在 **高级设置** 中配置（默认 10 分钟）。

---

## 项目结构

```
qq_with_openai/
├── config/
│   ├── default_config.json      # 运行时配置（自动生成）
│   ├── auth.json                # 认证信息（密码哈希、JWT密钥）
│   └── ip_bans.json             # IP 封禁持久化
├── backend/
│   ├── app.py                   # FastAPI 主应用 + 反向 WS 端点
│   ├── run.py                   # 启动入口
│   ├── api/
│   │   ├── routes.py            # 配置/状态/日志 API
│   │   ├── auth_routes.py       # 登录/登出/改密 API
│   │   ├── security_routes.py   # IP 封禁/安全规则 API
│   │   └── friend_routes.py     # 好友验证 Token API
│   ├── auth/
│   │   ├── auth_manager.py      # bcrypt + JWT 认证
│   │   └── dependencies.py      # FastAPI 认证依赖
│   ├── config/
│   │   └── config.py            # 配置读写管理
│   ├── models/
│   │   └── models.py            # Pydantic 请求/响应模型（含输入校验）
│   ├── security/
│   │   ├── ip_ban_manager.py    # IP 封禁核心逻辑
│   │   ├── ip_ban_middleware.py  # FastAPI 中间件
│   │   └── rules/               # 安全规则（速率/连接/行为/模式）
│   └── services/
│       ├── napcat_client.py     # NapCat WebSocket 通信
│       ├── message_handler.py   # 消息处理 + 多轮对话
│       ├── openai_service.py    # OpenAI API 调用
│       ├── image_processor.py   # 图片预处理
│       ├── face_config.py       # QQ 表情 ID → 文字映射
│       └── friend_verification.py # HMAC Token 生成/验证
├── frontend/
│   ├── index.html               # 管理面板入口
│   ├── token.html               # 好友验证 Token 页面（公开）
│   ├── css/                     # 样式（变量 + 主题）
│   └── js/
│       ├── app.js               # Vue 根实例
│       ├── api.js               # HTTP 请求封装
│       └── components/          # Vue 组件（各选项卡）
├── logs/
│   └── recent_messages.jsonl    # 消息日志（JSONL 滚动）
├── requirements.txt
└── README.md
```

## 配置说明

配置文件位于 `config/default_config.json`，所有配置项均可通过 Web 面板修改。

| 分类                            | 键                                   | 说明                  | 范围/默认值                       |
| ------------------------------- | ------------------------------------ | --------------------- | --------------------------------- |
| **openai**                | `baseurl`                          | API 地址              | 字符串，≤500                     |
|                                 | `apikey`                           | API 密钥              | 字符串，≤500                     |
|                                 | `model`                            | 模型名称              | 字符串，≤200                     |
|                                 | `max_tokens`                       | 最大 token 数         | 10–4096                          |
|                                 | `reply_timeout_sec`                | 回复超时(秒)          | 5–300                            |
|                                 | `reply_avg_length`                 | 平均回复长度          | 10–2000                          |
| **vision**                | `enabled`                          | 启用视觉模型          | bool                              |
|                                 | `use_reply_config`                 | 复用聊天模型配置      | bool                              |
|                                 | `baseurl` / `apikey` / `model` | 独立视觉模型配置      | 同 openai                         |
| **bot**                   | `prompt`                           | System Prompt         | ≤5000 字符                       |
|                                 | `auto_reply`                       | 自动回复              | bool                              |
|                                 | `group_only_at`                    | 群聊仅@时回复         | bool                              |
|                                 | `group_reply_at_all`               | @所有人也回复         | bool                              |
| **features**              | `emotion_conversion`               | 表情转义              | bool                              |
|                                 | `image_processing`                 | 图像识别              | bool（需视觉模型）                |
|                                 | `simulate_typing_enabled`          | 模拟打字              | bool                              |
|                                 | `typing_multiplier`                | 打字速度倍率          | 0.2–3.0                          |
|                                 | `context_enabled`                  | 启用上下文            | bool                              |
|                                 | `context_max_messages`             | 回溯轮数              | 1–200                            |
|                                 | `context_compression_enabled`      | 上下文压缩            | bool                              |
|                                 | `context_message_max_chars`        | 单条建议长度          | 0–5000，0=不限                   |
| **blacklist / whitelist** | `mode`                             | 模式                  | disabled / for_users / for_groups |
|                                 | `users` / `groups`               | ID 列表               | 纯数字字符串                      |
| **advanced**              | `napcat_url`                       | NapCat WS 地址        | 字符串                            |
|                                 | `napcat_token`                     | 连接 Token            | 字符串                            |
|                                 | `service_port`                     | 服务端口              | 1024–65535                       |
|                                 | `log_level`                        | 日志级别              | DEBUG/INFO/WARNING/ERROR          |
|                                 | `log_max_length`                   | 日志保留条数          | 20–2000                          |
|                                 | `session_expiry_hours`             | 会话有效时长(时)      | 0–8760，0=永不过期               |
|                                 | `friend_token_expiry_minutes`      | 好友 Token 有效期(分) | 1–1440                           |

## API 端点

### 公开端点

| 方法      | 路径                           | 说明                |
| --------- | ------------------------------ | ------------------- |
| GET       | `/`                          | 管理面板页面        |
| GET       | `/token`                     | 好友验证 Token 页面 |
| GET       | `/health`                    | 健康检查            |
| POST      | `/api/auth/login`            | 管理员登录          |
| GET       | `/api/auth/check`            | 检查登录状态        |
| POST      | `/api/friend/generate-token` | 生成好友验证 Token  |
| WebSocket | `/ws/napcat`                 | NapCat 反向 WS 接入 |

### 需认证端点（Cookie 鉴权）

| 方法   | 路径                              | 说明                   |
| ------ | --------------------------------- | ---------------------- |
| GET    | `/api/config`                   | 获取配置               |
| POST   | `/api/config`                   | 保存配置               |
| POST   | `/api/test-connection`          | 测试 OpenAI 连接       |
| GET    | `/api/status`                   | 获取运行状态与消息日志 |
| POST   | `/api/logs/clear`               | 清空消息日志           |
| POST   | `/api/auth/logout`              | 退出登录               |
| POST   | `/api/auth/change-password`     | 修改密码               |
| GET    | `/api/security/rules`           | 列出安全规则           |
| PUT    | `/api/security/rules/{rule_id}` | 修改安全规则           |
| GET    | `/api/security/bans`            | 列出封禁 IP            |
| POST   | `/api/security/bans`            | 手动封禁 IP            |
| DELETE | `/api/security/bans/{ip}`       | 解封 IP                |

## 消息处理流程

```
NapCat 反向 WebSocket 连入
        ↓
  napcat_client 解析 OneBot v11 事件
        ↓
  ┌─ 好友请求 → HMAC Token 验证 → 自动通过/拒绝
  └─ 聊天消息 ↓
        ├─ 检查自动回复开关
        ├─ 群聊：检查 @/引用
        ├─ 黑白名单过滤
        ├─ 表情转义（QQ 表情 CQ 码 → 文字描述）
        ├─ 图片分析（视觉模型，可选）
        ├─ 引用消息拼接
        ├─ 多轮对话历史构建
        ├─ OpenAI API 生成回复
        ├─ 上下文压缩（淘汰旧轮次，可选）
        ├─ 模拟打字延迟（可选）
        └─ 通过 NapCat 发送回复
```

## 安全机制

### 认证

- 首次启动自动生成随机密码（明文仅在终端打印一次）
- 密码使用 bcrypt 哈希存储（12 轮 salt）
- JWT 令牌存储在 HttpOnly + SameSite=Strict Cookie 中
- 支持 HTTPS 反向代理自动检测 `secure` 标志

### IP 安全

- 内置多维度安全规则：速率限制、连接频率、行为检测、请求模式
- 所有规则参数均可通过 API / 面板调整
- 自动封禁 + 手动封禁，支持封禁时长配置
- 封禁数据 JSON 持久化，服务重启不丢失
- 本地回环 IP 自动白名单

### 输入校验

- 所有 API 请求体使用 Pydantic 模型严格校验
- 数值字段均有范围限制（`ge` / `le`）
- 字符串字段有长度限制 + 空字节检测
- 黑白名单 ID 列表强制纯数字格式校验
- IP 地址格式校验（IPv4 / IPv6）
- 安全规则 ID 格式校验

## 故障排除

| 问题          | 排查方法                                                                              |
| ------------- | ------------------------------------------------------------------------------------- |
| NapCat 未连接 | 检查 NapCat 反向 WS 地址是否指向本服务 `ws://<IP>:<端口>/ws/napcat`；Token 是否一致 |
| AI 不回复     | 确认自动回复已开启；检查黑白名单；查看面板日志是否有 API 错误                         |
| 群聊不回复    | 检查"群聊仅@时回复"开关；确认 Bot 被直接 @ 或消息引用了 Bot                           |
| API 连接失败  | 使用面板"测试连接"验证；检查 Base URL 和 API Key                                      |
| 登录密码丢失  | 删除 `config/auth.json` 后重启服务，会重新生成                                      |
| 图片不识别    | 确认视觉模型已启用且配置正确；检查"图像识别处理"开关                                  |

## 许可证

MIT License
