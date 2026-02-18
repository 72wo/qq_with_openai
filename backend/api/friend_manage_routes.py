"""好友管理 API 路由"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/friends", tags=["好友管理"])


class DeleteFriendRequest(BaseModel):
    user_id: str = Field(..., min_length=5, max_length=12)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[1-9]\d{4,11}$", v):
            raise ValueError("QQ 号必须为 5-12 位数字且不以 0 开头")
        return v


@router.get("/list")
async def get_friend_list(auth: dict = Depends(require_auth)):
    """获取好友列表（需要认证）"""
    from ..app import app_state

    napcat_client = app_state.get("napcat_client")
    if not napcat_client or not napcat_client.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接，无法获取好友列表")

    try:
        friends = await napcat_client.get_friend_list()
        return {
            "success": True,
            "friends": friends,
            "total": len(friends),
        }
    except Exception as e:
        logger.error(f"获取好友列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取好友列表失败")


@router.delete("/delete")
async def delete_friend(body: DeleteFriendRequest, auth: dict = Depends(require_auth)):
    """删除好友（需要认证）"""
    from ..app import app_state

    napcat_client = app_state.get("napcat_client")
    if not napcat_client or not napcat_client.is_connected:
        raise HTTPException(status_code=503, detail="NapCat 未连接，无法执行操作")

    # 不允许删除 bot 自身
    login_info = await napcat_client.get_login_info()
    if login_info and login_info.get("user_id") == body.user_id:
        raise HTTPException(status_code=400, detail="不能删除 Bot 自身账号")

    try:
        success = await napcat_client.delete_friend(body.user_id)
        if success:
            logger.info(f"管理员删除好友: {body.user_id}")
            return {"success": True, "message": f"已删除好友: {body.user_id}"}
        else:
            raise HTTPException(status_code=500, detail="删除好友失败，请检查 NapCat 日志")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除好友异常: {e}")
        raise HTTPException(status_code=500, detail="删除好友操作异常")
