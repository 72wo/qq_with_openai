"""IP 封禁中间件"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI

from .rules.base import RequestContext

logger = logging.getLogger(__name__)

# 不检查的路径前缀（静态资源等）
_SKIP_PREFIXES = ("/static/", "/favicon.ico")


def _get_client_ip(request: Request) -> str:
    """提取真实客户端 IP"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


class IPBanMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 跳过静态资源
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        from ..app import app_state
        ban_manager = app_state.get("ip_ban_manager")
        if not ban_manager:
            return await call_next(request)

        ip = _get_client_ip(request)

        # 1. 检查是否已被封禁
        ban_info = ban_manager.is_banned(ip)
        if ban_info:
            remaining = ""
            if ban_info.get("expires"):
                remaining = f"，剩余 {max(0, int(ban_info['expires'] - time.time()))} 秒"
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"您的 IP 已被封禁: {ban_info.get('reason', '未知')}{remaining}",
                    "ban_info": {
                        "reason": ban_info.get("reason"),
                        "rule_id": ban_info.get("rule_id"),
                        "expires": ban_info.get("expires"),
                    }
                }
            )

        # 2. 构建请求上下文
        ctx = RequestContext(
            ip=ip,
            path=path,
            method=request.method,
            user_agent=request.headers.get("user-agent", ""),
            content_length=int(request.headers.get("content-length", 0) or 0),
            is_websocket=("upgrade" in request.headers.get("connection", "").lower()
                          and request.headers.get("upgrade", "").lower() == "websocket"),
            timestamp=time.time(),
        )

        # 3. 请求前检查（UA/注入/XSS/频率等）
        reason = ban_manager.check_request(ctx)
        if reason:
            return JSONResponse(
                status_code=403,
                content={"detail": f"请求被拒绝: {reason}"}
            )

        # 4. 正常处理请求
        response = await call_next(request)

        # 5. 响应后检查（404 扫描、401 认证失败等）
        ctx.status_code = response.status_code
        ctx.is_auth_failure = response.status_code == 401
        ctx.is_login_failure = (
            path == "/api/auth/login"
            and request.method == "POST"
            and response.status_code == 401
        )
        ban_manager.record_response(ctx)

        return response


def create_ip_ban_middleware(app: FastAPI) -> None:
    """注册 IP 封禁中间件"""
    app.add_middleware(IPBanMiddleware)
