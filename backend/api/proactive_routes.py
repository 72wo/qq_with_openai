"""主动消息管理 API 路由"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proactive", tags=["主动消息"])


# ── Pydantic 校验模型 ──────────────────────────────────

class StrategyConfig(BaseModel):
    enabled: Optional[bool] = None
    weight: Optional[float] = Field(default=None, ge=0.1, le=5.0)


class ProactiveConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    scope_mode: Optional[str] = Field(default=None, pattern=r"^(disabled|whitelist|blacklist)$")
    friend_whitelist: Optional[List[str]] = Field(default=None, max_length=500)
    friend_blacklist: Optional[List[str]] = Field(default=None, max_length=500)
    group_whitelist: Optional[List[str]] = Field(default=None, max_length=500)
    group_blacklist: Optional[List[str]] = Field(default=None, max_length=500)
    global_daily_max: Optional[int] = Field(default=None, ge=1, le=200)
    per_friend_daily_max: Optional[int] = Field(default=None, ge=1, le=50)
    per_group_daily_max: Optional[int] = Field(default=None, ge=1, le=30)
    min_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    active_hours_start: Optional[int] = Field(default=None, ge=0, le=23)
    active_hours_end: Optional[int] = Field(default=None, ge=1, le=24)
    strategies: Optional[Dict[str, StrategyConfig]] = None

    @field_validator("friend_whitelist", "friend_blacklist", "group_whitelist", "group_blacklist", mode="before")
    @classmethod
    def validate_id_list(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("必须为列表")
        for item in v:
            if not isinstance(item, str) or not re.match(r"^\d{1,15}$", item.strip()):
                raise ValueError(f"列表项必须为纯数字 ID: {item!r}")
        return [item.strip() for item in v]

    @field_validator("strategies", mode="before")
    @classmethod
    def validate_strategies(cls, v):
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("strategies 必须为对象")
        # 限制策略 ID 为已知值（防止注入）
        from ..services.proactive_scheduler import STRATEGY_IDS
        for key in v:
            if key not in STRATEGY_IDS:
                raise ValueError(f"未知的策略 ID: {key}")
        return v


# ── API 端点 ──────────────────────────────────────────

@router.get("/config")
async def get_proactive_config(auth: dict = Depends(require_auth)):
    """获取主动消息配置"""
    from ..app import app_state
    from ..services.proactive_scheduler import get_default_proactive_config

    config = app_state.get("config")
    if not config:
        raise HTTPException(status_code=500, detail="配置服务未初始化")

    pc = config.get("proactive", None)
    if pc is None:
        pc = get_default_proactive_config()

    return {"success": True, "data": pc}


@router.post("/config")
async def save_proactive_config(body: ProactiveConfigUpdate, auth: dict = Depends(require_auth)):
    """保存主动消息配置"""
    from ..app import app_state
    from ..services.proactive_scheduler import get_default_proactive_config

    config = app_state.get("config")
    if not config:
        raise HTTPException(status_code=500, detail="配置服务未初始化")

    # 获取或初始化 proactive 配置
    all_config = config.get_all()
    if "proactive" not in all_config:
        all_config["proactive"] = get_default_proactive_config()

    pc = all_config["proactive"]

    # 合并更新（仅覆盖非 None 字段）
    update = body.model_dump(exclude_none=True)
    for key, val in update.items():
        if key == "strategies" and isinstance(val, dict):
            if "strategies" not in pc:
                pc["strategies"] = {}
            for sid, scfg in val.items():
                if sid not in pc["strategies"]:
                    pc["strategies"][sid] = {}
                if isinstance(scfg, dict):
                    pc["strategies"][sid].update(scfg)
        else:
            pc[key] = val

    # 安全约束: active_hours_start 和 end 不能相同
    if pc.get("active_hours_start", 8) == pc.get("active_hours_end", 23):
        raise HTTPException(status_code=400, detail="活跃时间起止不能相同")

    config.update_config(all_config)

    # 通知调度器重启
    scheduler = app_state.get("proactive_scheduler")
    if scheduler:
        scheduler.restart()

    return {"success": True, "message": "主动消息配置已保存"}


@router.get("/status")
async def get_proactive_status(auth: dict = Depends(require_auth)):
    """获取调度器运行状态"""
    from ..app import app_state

    scheduler = app_state.get("proactive_scheduler")
    if not scheduler:
        return {
            "success": True,
            "data": {
                "running": False,
                "enabled": False,
                "total_sent_today": 0,
                "total_sent_all": 0,
                "daily_limit": 0,
                "last_sent_time": None,
                "last_strategy": None,
                "last_target": None,
                "next_action_in": 0,
            },
        }

    return {"success": True, "data": scheduler.get_status()}


@router.get("/strategies")
async def get_strategies(auth: dict = Depends(require_auth)):
    """获取所有策略定义（前端渲染用）"""
    from ..services.proactive_scheduler import ProactiveScheduler

    return {
        "success": True,
        "strategies": ProactiveScheduler.get_strategy_definitions(),
    }


@router.post("/trigger")
async def manual_trigger(auth: dict = Depends(require_auth)):
    """手动触发一次主动消息（调试用）"""
    from ..app import app_state

    scheduler = app_state.get("proactive_scheduler")
    if not scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    if not scheduler._running:
        raise HTTPException(status_code=400, detail="调度器未运行，请先启用主动消息功能")

    napcat = app_state.get("napcat_client")
    if not napcat or not napcat.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接")

    try:
        await scheduler._perform_action()
        return {"success": True, "message": "已触发一次主动消息"}
    except Exception as e:
        logger.error(f"手动触发主动消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"触发失败: {str(e)}")
