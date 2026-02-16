"""好友验证 Token API 路由"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/friend", tags=["好友验证"])


class GenerateTokenRequest(BaseModel):
    qq_number: str = Field(..., min_length=5, max_length=12)

    @field_validator("qq_number")
    @classmethod
    def validate_qq(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.match(r"^[1-9]\d{4,11}$", v):
            raise ValueError("QQ 号必须为 5-12 位数字且不以 0 开头")
        return v


@router.post("/generate-token")
async def generate_token(body: GenerateTokenRequest):
    """公开端点: 生成好友验证 Token (受 IP 限流保护)"""
    from ..app import app_state

    service = app_state.get("friend_verification")
    if not service:
        raise HTTPException(status_code=500, detail="好友验证服务未初始化")

    try:
        token = service.generate_token(body.qq_number)
        return {
            "success": True,
            "token": token,
            "message": "请将此 Token 作为好友验证消息发送",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"生成 Token 失败: {e}")
        raise HTTPException(status_code=500, detail="Token 生成失败")
