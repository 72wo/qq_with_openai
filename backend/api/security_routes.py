"""IP 封禁管理 API 路由"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["安全"])


class BanRequest(BaseModel):
    ip: str = Field(..., min_length=1, max_length=45)
    reason: str = Field(default="手动封禁", max_length=200)
    duration_sec: int = Field(default=3600, ge=60, le=2592000)  # 1 min ~ 30 days


class RuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    threshold: Optional[int] = Field(default=None, ge=1, le=100000)
    window_sec: Optional[int] = Field(default=None, ge=1, le=86400)
    ban_duration_sec: Optional[int] = Field(default=None, ge=10, le=2592000)


@router.get("/rules")
async def list_rules(auth: dict = Depends(require_auth)):
    """列出所有安全规则及配置"""
    from ..app import app_state
    ban_manager = app_state.get("ip_ban_manager")
    if not ban_manager:
        raise HTTPException(status_code=500, detail="IP 封禁服务未初始化")
    return {"rules": ban_manager.get_rules()}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate, auth: dict = Depends(require_auth)):
    """修改安全规则参数"""
    from ..app import app_state
    ban_manager = app_state.get("ip_ban_manager")
    if not ban_manager:
        raise HTTPException(status_code=500, detail="IP 封禁服务未初始化")

    data = body.model_dump(exclude_none=True)
    if not ban_manager.update_rule(rule_id, data):
        raise HTTPException(status_code=404, detail="规则不存在")

    return {"success": True, "message": f"规则 {rule_id} 已更新"}


@router.get("/bans")
async def list_bans(auth: dict = Depends(require_auth)):
    """列出所有封禁 IP"""
    from ..app import app_state
    ban_manager = app_state.get("ip_ban_manager")
    if not ban_manager:
        raise HTTPException(status_code=500, detail="IP 封禁服务未初始化")
    return {"bans": ban_manager.get_bans()}


@router.post("/bans")
async def ban_ip(body: BanRequest, auth: dict = Depends(require_auth)):
    """手动封禁 IP"""
    from ..app import app_state
    ban_manager = app_state.get("ip_ban_manager")
    if not ban_manager:
        raise HTTPException(status_code=500, detail="IP 封禁服务未初始化")

    ban_manager.ban_ip(
        ip=body.ip,
        reason=body.reason,
        duration_sec=body.duration_sec,
        rule_id="manual",
        manual=True,
    )
    return {"success": True, "message": f"已封禁 IP: {body.ip}"}


@router.delete("/bans/{ip:path}")
async def unban_ip(ip: str, auth: dict = Depends(require_auth)):
    """解封 IP"""
    from ..app import app_state
    ban_manager = app_state.get("ip_ban_manager")
    if not ban_manager:
        raise HTTPException(status_code=500, detail="IP 封禁服务未初始化")

    if not ban_manager.unban_ip(ip):
        raise HTTPException(status_code=404, detail="该 IP 未被封禁")

    return {"success": True, "message": f"已解封 IP: {ip}"}
