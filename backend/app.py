"""FastAPI 主应用"""

import asyncio
import logging
import os
import json
from collections import deque
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from .config import Config
from .services import NapcatClient, MessageHandler
from .auth import AuthManager
from .api import routes
from .api import auth_routes
from .api import security_routes
from .api import friend_routes
from .api import friend_manage_routes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局状态
app_state = {
    "config": None,
    "napcat_client": None,
    "message_handler": None,
    "napcat_task": None,
    "auth_manager": None,
    "ip_ban_manager": None,
    "friend_verification": None,
}


def get_log_max_length() -> int:
    config = app_state.get("config")
    if not config:
        return 200
    value = config.get("advanced.log_max_length", 200)
    try:
        parsed = int(value)
        return max(20, min(parsed, 2000))
    except Exception:
        return 200


def get_log_file_path() -> Path:
    root_path = Path(__file__).parent.parent
    log_file = root_path / "logs" / "recent_messages.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if not log_file.exists():
        log_file.touch()
    return log_file


def append_recent_message(entry: dict):
    log_file = get_log_file_path()
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    max_len = get_log_max_length()
    compact_keep = max(max_len * 2, 400)
    if log_file.stat().st_size > 5 * 1024 * 1024:
        recent_entries = get_recent_messages(compact_keep)
        with open(log_file, "w", encoding="utf-8") as file:
            for log_entry in recent_entries:
                file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def get_recent_messages(limit: int | None = None) -> list[dict]:
    max_len = get_log_max_length() if limit is None else max(1, int(limit))
    log_file = get_log_file_path()
    buffer: deque[dict] = deque(maxlen=max_len)

    with open(log_file, "r", encoding="utf-8") as file:
        for line in file:
            text = line.strip()
            if not text:
                continue
            try:
                buffer.append(json.loads(text))
            except json.JSONDecodeError:
                continue

    # 返回倒序（最新的消息在前）
    return list(reversed(buffer))


def clear_recent_messages():
    log_file = get_log_file_path()
    with open(log_file, "w", encoding="utf-8") as file:
        file.write("")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    logger.info("应用启动中...")

    # 初始化配置
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_config.json")
    app_state["config"] = Config(config_path)

    # 应用配置中的日志级别
    log_level = app_state["config"].get("advanced.log_level", "INFO")
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    # 初始化认证管理器
    auth_path = os.path.join(os.path.dirname(__file__), "..", "config", "auth.json")
    app_state["auth_manager"] = AuthManager(auth_path)
    app_state["auth_manager"].initialize()

    # 初始化 IP 封禁管理器
    from .security import IPBanManager
    ip_bans_path = os.path.join(os.path.dirname(__file__), "..", "config", "ip_bans.json")
    app_state["ip_ban_manager"] = IPBanManager(ip_bans_path)

    # 初始化好友验证服务
    from .services.friend_verification import FriendVerificationService
    friend_secret = app_state["auth_manager"].friend_verification_secret
    friend_token_minutes = app_state["config"].get("advanced.friend_token_expiry_minutes", 10)
    app_state["friend_verification"] = FriendVerificationService(friend_secret, window_sec=friend_token_minutes * 60)

    # 初始化 napcat 客户端
    napcat_url = app_state["config"].get("advanced.napcat_url", "ws://localhost:8080/ws/napcat")
    napcat_token = app_state["config"].get("advanced.napcat_token", "")
    app_state["napcat_client"] = NapcatClient(napcat_url, napcat_token, app_state["config"])

    # 初始化消息处理器
    app_state["message_handler"] = MessageHandler(app_state["config"], app_state["napcat_client"])

    # 设置消息处理回调
    app_state["napcat_client"].set_message_handler(app_state["message_handler"].handle_message)

    # 设置好友验证回调
    app_state["napcat_client"].set_friend_verification_service(app_state["friend_verification"])

    # 纯服务端模式：不主动发起连接，只等待 NapCat 反向连接
    logger.info("NapCat 服务端模式已启动，等待反向 WebSocket 连接...")
    # 确保 task 初始化为 None，防止后续逻辑报错
    app_state["napcat_task"] = None

    # 启动 tracker 定期清理任务（每 30 分钟清理一次过期 IP 追踪数据）
    async def _periodic_cleanup():
        while True:
            await asyncio.sleep(1800)
            try:
                ban_manager = app_state.get("ip_ban_manager")
                if ban_manager:
                    ban_manager.cleanup_trackers()
                    logger.debug("IP tracker 定期清理完成")
            except Exception as e:
                logger.error(f"IP tracker 定期清理失败: {e}")

    app_state["cleanup_task"] = asyncio.create_task(_periodic_cleanup())

    logger.info("应用启动完成")

    yield

    # 关闭事件
    logger.info("应用关闭中...")
    if app_state.get("cleanup_task"):
        app_state["cleanup_task"].cancel()
    if app_state["napcat_task"]:
        app_state["napcat_task"].cancel()
    if app_state["napcat_client"]:
        await app_state["napcat_client"].disconnect()
    # 持久化 IP 封禁数据
    if app_state.get("ip_ban_manager"):
        app_state["ip_ban_manager"].save()
    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="QQ 机器人 OpenAI 集成",
    description="基于 napcat WebSocket 的 QQ 机器人",
    version="1.0.0",
    lifespan=lifespan
)


def get_message_handler() -> MessageHandler:
    return app_state["message_handler"]


# IP 封禁中间件（必须在路由之前注册）
from .security.ip_ban_middleware import create_ip_ban_middleware
create_ip_ban_middleware(app)

# 包含 API 路由
app.include_router(auth_routes.router)
app.include_router(security_routes.router)
app.include_router(friend_routes.router)
app.include_router(friend_manage_routes.router)
app.include_router(routes.router)


# 静态文件服务
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


# 根路径：禁止直接访问（返回 403）
@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
async def root_forbidden():
    """禁止直接访问根目录（用于安全/隐藏管理面板入口）"""
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})


# 管理控制台（SPA）路由 — 提供给 /admin 及其子路径，用于客户端路由支持
@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
@app.get("/admin/{full_path:path}", include_in_schema=False)
async def admin_panel(full_path: str | None = None):
    html_file = frontend_path / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return JSONResponse(status_code=404, content={"detail": "页面不存在"})


# Token 页面路由（公开页面）
@app.get("/token")
async def token_page():
    """返回好友验证 Token 页面"""
    html_file = frontend_path / "token.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "页面不存在"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.websocket("/ws/napcat")
async def napcat_reverse_ws(websocket: WebSocket):
    """接收 NapCat 反向 WebSocket 连接"""
    config = app_state.get("config")
    expected_token = config.get("advanced.napcat_token", "") if config else ""
    query_token = websocket.query_params.get("access_token", "")
    auth_header = websocket.headers.get("authorization", "")
    auth_token = ""
    if auth_header.lower().startswith("bearer "):
        auth_token = auth_header[7:].strip()

    if expected_token and expected_token not in {query_token, auth_token}:
        await websocket.close(code=1008, reason="Invalid token")
        logger.warning("NapCat 反向连接鉴权失败")
        return

    await websocket.accept()
    napcat_client = app_state.get("napcat_client")
    if not napcat_client:
        await websocket.close(code=1011, reason="Server not ready")
        return

    napcat_client.attach_external_websocket(websocket)
    logger.info("NapCat 反向 WebSocket 已建立")

    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                await napcat_client._handle_payload(data)
            except json.JSONDecodeError:
                logger.error("无法解析 NapCat 反向消息")
    except WebSocketDisconnect:
        logger.warning("NapCat 反向 WebSocket 已断开")
        napcat_client.mark_external_disconnected()
    except Exception as e:
        logger.error(f"NapCat 反向 WebSocket 处理异常: {str(e)}")
        napcat_client.mark_external_disconnected()


if __name__ == "__main__":
    import uvicorn

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_config.json")
    runtime_config = Config(config_path)
    config_port = runtime_config.get("advanced.service_port", 5000)

    port = int(os.getenv("FLASK_PORT", config_port))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=debug)
