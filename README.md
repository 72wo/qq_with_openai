# QQ 机器人 OpenAI 集成方案

基于 napcat WebSocket 客户端，实现一个完整的 QQ 机器人 OpenAI 自动回复系统，包含 Web UI 配置界面。

## 项目特性

- 🤖 **自动回复**：支持私聊和群聊，群聊可设置仅@时回复
- 🧠 **AI 集成**：灵活配置 OpenAI API，支持自定义 baseurl、apikey、model
- 🖼️ **图像分析**：启用视觉模型可分析消息中的图像
- 😊 **表情转义**：自动将 AI 回复中的 emoji 转换为 QQ 表情代码
- 🛡️ **黑白名单**：支持用户和群聊的黑白名单管理
- 🎛️ **Web UI**：现代化配置界面，支持多选项卡操作
- ⚡ **异步处理**：基于 FastAPI 和 asyncio 的高性能架构

## 系统要求

- Python 3.8+
- pip（Python 包管理器）
- napcat 服务运行中（WebSocket 服务）
- OpenAI API 密钥

## 安装步骤

### 1. 克隆项目或下载源码

```bash
cd qq_with_openai
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 启动服务

```bash
# 进入项目根目录
cd /path/to/qq_with_openai

# 方式 A：按配置文件 advanced.service_port 启动（推荐）
python -m backend.run

# 方式 B：直接使用 uvicorn（不读取配置文件端口，需要手动指定）
python -m uvicorn backend.app:app --reload --port 5000
```

服务启动后，访问 `http://localhost:5000` 打开配置面板

### 2. 配置 OpenAI

1. 在 Web UI 中打开 **OpenAI 配置** 选项卡
2. 填写：
   - **Base URL**：OpenAI API 地址（默认 https://api.openai.com/v1，可使用代理地址）
   - **API Key**：你的 OpenAI API 密钥
   - **Model**：使用的模型（如 gpt-4, gpt-3.5-turbo）
   - **启用视觉模型**：如需要分析图像则开启
3. 点击 **测试连接** 验证配置

### 3. 配置 napcat 连接

在 **高级设置** 选项卡中配置：
- **napcat WebSocket URL**：默认 `ws://localhost:8080/ws/napcat`
- 确保 napcat 服务正常运行

### 4. 自定义 AI 提示词

在 **自定义设置** 选项卡配置：
- **System Prompt**：AI 的系统提示（决定 AI 的角色和行为）
- **自动回复**：是否启用自动回复
- **群聊仅@时回复**：群聊中是否只回复被@的消息
- **图像处理**：是否处理消息中的图像
- **表情转义**：是否转换表情符号

### 5. 配置黑白名单

在 **黑白名单** 选项卡中：

**黑名单模式**：
1. 选择 **模式** 为 "用户黑名单" 或 "群聊黑名单"
2. 在输入框中输入要屏蔽的 ID（每行一个）
3. 点击 **添加到黑名单**

**白名单模式**：
1. 选择 **模式** 为 "用户白名单" 或 "群聊白名单"
2. 在输入框中输入允许的 ID（每行一个）
3. 点击 **添加到白名单**

### 6. 保存配置

点击页面底部的 **保存配置** 按钮，配置将保存到 `backend/config/default_config.json`

## 配置文件说明

配置文件位置：`backend/config/default_config.json`

配置结构：

```json
{
  "openai": {
    "baseurl": "https://api.openai.com/v1",
    "apikey": "sk-...",
    "model": "gpt-4",
    "vision_enabled": false
  },
  "bot": {
    "prompt": "你是一个有帮助的 AI 助手",
    "auto_reply": true,
    "group_only_at": true
  },
  "blacklist": {
    "mode": "enabled",
    "users": ["123456", "789012"],
    "groups": ["111111"],
    "exceptions": []
  },
  "whitelist": {
    "mode": "disabled",
    "users": [],
    "groups": [],
    "exceptions": []
  },
  "features": {
    "image_processing": true,
    "emotion_conversion": true
  },
  "advanced": {
    "napcat_url": "ws://localhost:8080/ws/napcat",
    "service_port": 5000,
    "log_level": "INFO"
  }
}
```

## API 端点说明

### GET `/api/config`
获取当前配置

**响应**：
```json
{
  "id": "config",
  "data": { /* 配置对象 */ }
}
```

### POST `/api/config`
保存配置

**请求体**：
```json
{
  "openai": { /* openai 配置 */ },
  "bot": { /* bot 配置 */ }
  // ... 其他配置字段
}
```

### POST `/api/test-connection`
测试 OpenAI API 连接

**请求体**：
```json
{
  "baseurl": "https://api.openai.com/v1",
  "apikey": "sk-...",
  "model": "gpt-4"
}
```

**响应**：
```json
{
  "success": true,
  "message": "连接成功"
}
```

### GET `/health`
健康检查

**响应**：
```json
{
  "status": "healthy",
  "napcat_connected": true,
  "config_loaded": true
}
```

## 消息处理流程

```
napcat WebSocket 消息
    ↓
消息处理器 (MessageHandler)
    ├─ 检查消息类型 (private/group)
    ├─ 群聊检查是否被@
    ├─ 黑白名单检查
    └─ 通过 → OpenAI API 调用
                  ↓
              生成回复文本
                  ↓
              图像分析（如果启用）
                  ↓
              表情转义（如果启用）
                  ↓
              napcat 发送回复
```

## 项目结构

```
qq_with_openai/
├── backend/
│   ├── app.py                      # FastAPI 主应用
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.py              # 配置管理
│   │   └── default_config.json    # 默认配置文件
│   ├── services/
│   │   ├── __init__.py
│   │   ├── napcat_client.py       # napcat WebSocket 客户端
│   │   ├── openai_service.py      # OpenAI API 集成
│   │   ├── message_handler.py     # 消息处理逻辑
│   │   ├── image_processor.py     # 图像处理
│   │   └── face_config.py         # QQ表情ID映射配置
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py              # 数据模型
│   └── api/
│       ├── __init__.py
│       └── routes.py              # REST API 路由
├── frontend/
│   ├── index.html                 # Web UI
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js                 # (已在 HTML 中内联)
│   │   └── api.js                 # (已在 HTML 中内联)
│   └── img/                       # 图片资源
├── requirements.txt               # Python 依赖
└── README.md                      # 本文件
```

## 功能说明

### 消息自动回复
- **私聊**：收到任何消息立即回复
- **群聊**：默认只回复被@的消息（可通过 `bot.group_only_at` 修改）

### 黑白名单管理
- **黑名单模式**：禁止指定用户/群聊向机器人发送消息
- **白名单模式**：只允许指定用户/群聊向机器人发送消息
- 可在两种模式间切换

### 图像分析
- 启用 `openai.vision_enabled` 时，AI 可以分析消息中的图像
- 图像会被自动转换为适合 Vision API 的格式
- 图像分析结果会融入 AI 的回复上下文

### 表情转义
- 启用 `features.emotion_conversion` 时，AI 回复中的 emoji（😊） 会自动转换为 QQ 表情代码（[愉快]）
- 包含常见的百余个 emoji 和对应的 QQ 表情映射

## 故障排除

### 连接 napcat 失败
1. 确保 napcat 服务已启动
2. 检查高级设置中的 WebSocket URL 是否正确
3. 查看日志输出是否有连接错误提示

### OpenAI API 连接失败
1. 检查 API Key 是否正确无误
2. 确保网络连接正常
3. 如使用代理，确保 baseurl 配置正确
4. 使用"测试连接"功能验证配置

### Web UI 无法加载
1. 确保 FastAPI 服务正常运行
2. 检查浏览器控制台是否有错误
3. 尝试清除浏览器缓存并重新刷新页面

### 消息不回复
1. 检查 `bot.auto_reply` 是否启用
2. 确认发送者不在黑名单中
3. 如启用白名单，确认发送者在白名单中
4. 查看 Web UI 的状态监控选项卡是否有错误日志

## 环境变量

可以通过环境变量覆盖默认配置：

```bash
export FLASK_PORT=5000            # 服务端口
export FLASK_DEBUG=False          # 调试模式
export NAPCAT_WS_URL=ws://...     # napcat WebSocket URL
```

## 示例使用

### 配置一个知识库助手

**System Prompt**：
```
你是一个文物知识专家。用户询问的问题可能涉及历史、考古、博物馆等相关内容。
请根据你的知识库回答问题，如果不确定，请说明你不确定。
```

### 配置一个翻译机器人

**System Prompt**：
```
你是一个翻译助手。用户的消息可能是中文、英文或其他语言。
请检测消息的语言，如果是中文则翻译为英文，如果是其他语言则翻译为中文。
只返回翻译结果，不需要额外说明。
```

## 开发指南

### QQ表情映射

QQ表情通过 `backend/services/face_config.py` 中的 `QQ_FACE_MAP` 字典进行映射，将表情ID转换为文字描述供AI理解。

```python
QQ_FACE_MAP = {
    0: "惊讶",
    1: "撇嘴",
    2: "色",
    # ... 更多映射
}
```

### 自定义消息处理逻辑

编辑 `backend/services/message_handler.py` 的 `handle_message` 方法来实现自定义逻辑。

### 扩展 API 端点

在 `backend/api/routes.py` 中添加新的路由：

```python
@router.get("/api/custom-endpoint")
async def custom_endpoint():
    return {"custom": "response"}
```

## 注意事项

1. **API 密钥安全**：不要将 API Key 提交到版本控制系统，使用环境变量或 `.env` 文件
2. **费用监控**：OpenAI API 调用会产生费用，请监控使用情况
3. **速率限制**：注意 OpenAI API 的速率限制
4. **日志大小**：长时间运行时注意日志文件大小

## 许可证

此项目遵循 MIT 许可证。

## 贡献

欢迎提交 issue 和 pull request！

## 支持

如有问题，请提交 GitHub Issue 或联系开发者。

## 版本历史

- v1.0.0 (2024-02-14)：初始版本发布
  - 完整的 napcat WebSocket 集成
  - OpenAI API 集成
  - Web UI 配置面板
  - 黑白名单管理
  - 图像分析支持
  - 表情转义功能

## 更新日志

### 计划功能

- [ ] 数据库持久化（SQLite）
- [ ] 消息历史记录
- [ ] 插件系统
- [ ] Docker 部署
- [ ] 多语言支持
- [ ] 对话上下文管理
