"""主动消息管理 API 路由（支持按 bot 账号区分配置）"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proactive", tags=["主动消息"])


# ── 工具：获取当前 bot QQ 账号 ──────────────────────────

async def _get_bot_qq(app_state: dict) -> Optional[str]:
    """获取当前连接的 bot QQ 号，用于按账号区分配置"""
    napcat = app_state.get("napcat_client")
    if not napcat or not napcat.is_connected:
        return None
    try:
        info = await napcat.get_login_info()
        if info:
            return str(info.get("user_id", "")).strip() or None
    except Exception:
        pass
    return None


def _get_account_config(all_config: dict, bot_qq: Optional[str], default_factory) -> dict:
    """获取或创建指定账号的主动消息配置"""
    ba = all_config.setdefault("proactive_by_account", {})
    key = bot_qq or "default"
    if key not in ba:
        ba[key] = default_factory()
    return ba[key]


# ── Pydantic 校验模型 ──────────────────────────────────

class StrategyConfig(BaseModel):
    enabled: Optional[bool] = None
    weight: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    # 自定义时间范围，支持小时（整数）、分钟（整数，0-1440）或字符串格式 'HH:MM'，统一保存为分钟整数列表 [start_min, end_min]
    time_range: Optional[List[int]] = None
    # 自定义目标类型，允许 "friend" / "group"
    target_types: Optional[List[str]] = None

    @field_validator("time_range", mode="before")
    @classmethod
    def validate_time_range(cls, v):
        """支持的输入格式：
        - [6, 10] (表示小时，向后兼容)
        - [360, 600] (表示分钟)
        - ['06:00', '10:30'] (字符串)
        返回统一的分钟整数列表 [start_min, end_min]
        """
        if v is None:
            return v
        if not isinstance(v, list) or len(v) != 2:
            raise ValueError("time_range 必须为包含 2 个元素的列表")

        def to_minutes(x):
            # 整数：如果 <=24 视为小时，否则视为分钟
            if isinstance(x, int):
                if 0 <= x <= 24:
                    return x * 60
                if 0 <= x <= 1440:
                    return x
                raise ValueError("整数时间必须为小时(0-24)或分钟(0-1440)")
            # 字符串：HH:MM
            if isinstance(x, str):
                m = re.match(r"^(\d{1,2}):(\d{2})$", x.strip())
                if not m:
                    raise ValueError(f"无效的时间格式: {x!r}，应为 'HH:MM'")
                hh = int(m.group(1))
                mm = int(m.group(2))
                if not (0 <= hh <= 24 and 0 <= mm < 60):
                    raise ValueError(f"时间超出范围: {x!r}")
                total = hh * 60 + mm
                if total > 1440:
                    raise ValueError(f"时间超出范围: {x!r}")
                return total
            raise ValueError("time_range 元素必须为整数或 'HH:MM' 字符串")

        start_min = to_minutes(v[0])
        end_min = to_minutes(v[1])

        if not (0 <= start_min < end_min <= 1440):
            raise ValueError("time_range 必须满足 0 <= start < end <= 1440")

        return [start_min, end_min]

    @field_validator("target_types", mode="before")
    @classmethod
    def validate_target_types(cls, v):
        if v is None:
            return v
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("target_types 不能为空列表")
        allowed = {"friend", "group"}
        for t in v:
            if t not in allowed:
                raise ValueError(f"无效的目标类型: {t!r}，允许值: {allowed}")
        return list(set(v))


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

    all_config = config.get_all()
    pc = all_config.get("proactive")
    if not pc:
        pc = get_default_proactive_config()

    bot_qq = await _get_bot_qq(app_state)
    return {"success": True, "data": pc, "bot_qq": bot_qq}


@router.post("/config")
async def save_proactive_config(body: ProactiveConfigUpdate, auth: dict = Depends(require_auth)):
    """保存主动消息配置（专用端点，带 Pydantic 校验）"""
    from ..app import app_state
    from ..services.proactive_scheduler import get_default_proactive_config

    config = app_state.get("config")
    if not config:
        raise HTTPException(status_code=500, detail="配置服务未初始化")

    all_config = config.get_all()
    pc = all_config.setdefault("proactive", get_default_proactive_config())

    # 合并更新（仅覆盖非 None 字段）
    update = body.model_dump(exclude_none=True)
    for key, val in update.items():
        if key == "strategies" and isinstance(val, dict):
            pc.setdefault("strategies", {})
            for sid, scfg in val.items():
                pc["strategies"].setdefault(sid, {})
                if isinstance(scfg, dict):
                    pc["strategies"][sid].update(scfg)
        else:
            pc[key] = val

    # 安全约束: active_hours_start 和 end 不能相同
    if pc.get("active_hours_start", 8) == pc.get("active_hours_end", 23):
        raise HTTPException(status_code=400, detail="活跃时间起止不能相同")

    config.update_config(all_config)

    # 通知调度器重载
    scheduler = app_state.get("proactive_scheduler")
    if scheduler:
        scheduler.restart()

    bot_qq = await _get_bot_qq(app_state)
    return {"success": True, "message": "主动消息配置已保存", "bot_qq": bot_qq}


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
    """手动触发一次主动消息（纯测试功能，绕过所有调度限制）"""
    from ..app import app_state

    scheduler = app_state.get("proactive_scheduler")
    if not scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    napcat = app_state.get("napcat_client")
    if not napcat or not napcat.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接")

    try:
        ok = await scheduler.manual_trigger()
        if ok:
            return {"success": True, "message": "已触发一次主动消息（测试）"}
        else:
            return {"success": False, "message": "触发失败：无可用目标或策略，请检查白名单和策略配置"}
    except Exception as e:
        logger.error(f"手动触发主动消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"触发失败: {str(e)}")
