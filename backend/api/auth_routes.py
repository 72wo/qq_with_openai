"""认证相关 API 路由"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 请求模型 ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


# ── 路由 ──────────────────────────────────────────────────
@router.post("/login")
async def login(body: LoginRequest, request: Request):
    """管理员登录 — 根据请求协议动态设置 Cookie 的 `secure` 标志。

    - 若请求是 HTTPS 或通过反向代理且 `x-forwarded-proto: https`，则设置 secure=True。
    - 本地 HTTP 访问（开发场景）则设置 secure=False，避免浏览器不保存 Cookie 导致无法保持登录。
    """
    from ..app import app_state

    auth_manager = app_state.get("auth_manager")
    if not auth_manager:
        raise HTTPException(status_code=500, detail="认证服务未初始化")

    if not auth_manager.verify_password(body.password):
        logger.warning("登录失败: 密码错误")
        raise HTTPException(status_code=401, detail="密码错误")

    token = auth_manager.create_token()
    response = JSONResponse(content={"success": True, "message": "登录成功"})

    # 动态判断是否应设置 secure cookie：优先检查 x-forwarded-proto（反代），否则使用 request.url.scheme
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    secure_cookie = (request.url.scheme == "https") or (forwarded_proto == "https")

    # 在本地 HTTP 开发时不设置 secure，以便浏览器能保存会话 Cookie；在 HTTPS/公网场景下保持 secure=True
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="strict",
        max_age=86400,
        path="/",
    )
    logger.info(f"管理员登录成功 (secure_cookie={secure_cookie}, scheme={request.url.scheme}, xfp={forwarded_proto})")
    return response


@router.post("/logout")
async def logout(auth: dict = Depends(require_auth)):
    """退出登录"""
    response = JSONResponse(content={"success": True, "message": "已退出登录"})
    response.delete_cookie(key="session_token", path="/")
    return response


@router.get("/check")
async def check_auth(request: Request):
    """检查当前登录状态（公开端点，手动验证 Cookie）"""
    from ..app import app_state

    auth_manager = app_state.get("auth_manager")
    if not auth_manager:
        return JSONResponse(status_code=500, content={"authenticated": False})

    token = request.cookies.get("session_token")
    if not token:
        return JSONResponse(status_code=401, content={"authenticated": False})

    payload = auth_manager.validate_token(token)
    if payload is None:
        return JSONResponse(status_code=401, content={"authenticated": False})

    return {"authenticated": True}


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, auth: dict = Depends(require_auth)):
    """修改密码"""
    from ..app import app_state

    auth_manager = app_state.get("auth_manager")
    if not auth_manager:
        raise HTTPException(status_code=500, detail="认证服务未初始化")

    if not auth_manager.change_password(body.old_password, body.new_password):
        raise HTTPException(status_code=400, detail="当前密码错误")

    return {"success": True, "message": "密码修改成功，请重新登录"}
