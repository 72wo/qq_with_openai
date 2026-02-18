"""群组管理 API 路由"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/groups", tags=["群组管理"])


class QuitGroupRequest(BaseModel):
    group_id: str = Field(..., min_length=5, max_length=12)

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{5,12}$", v):
            raise ValueError("群号必须为 5-12 位纯数字")
        return v


@router.get("/list")
async def get_group_list(auth: dict = Depends(require_auth)):
    """获取群组列表（需要认证）"""
    from ..app import app_state

    napcat_client = app_state.get("napcat_client")
    if not napcat_client or not napcat_client.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接，无法获取群组列表")

    try:
        groups = await napcat_client.get_group_list()
        return {
            "success": True,
            "groups": groups,
            "total": len(groups),
        }
    except Exception as e:
        logger.error(f"获取群组列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取群组列表失败")


@router.delete("/quit")
async def quit_group(body: QuitGroupRequest, auth: dict = Depends(require_auth)):
    """退出群组（需要认证）"""
    from ..app import app_state

    napcat_client = app_state.get("napcat_client")
    if not napcat_client or not napcat_client.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接，无法执行操作")

    try:
        success = await napcat_client.quit_group(body.group_id)
        if success:
            logger.info(f"管理员退出群组: {body.group_id}")
            return {"success": True, "message": f"已退出群组: {body.group_id}"}
        else:
            raise HTTPException(status_code=500, detail="退出群组失败，请检查 NapCat 日志")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"退出群组异常: {e}")
        raise HTTPException(status_code=500, detail="退出群组操作异常")
