"""FastAPI 认证依赖"""

from fastapi import Request, HTTPException


async def require_auth(request: Request) -> dict:
    """从 HttpOnly Cookie 中验证 JWT，返回 payload 或抛出 401。"""
    from ..app import app_state

    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    auth_manager = app_state.get("auth_manager")
    if not auth_manager:
        raise HTTPException(status_code=500, detail="认证服务未初始化")

    payload = auth_manager.validate_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期")

    return payload
