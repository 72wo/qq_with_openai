from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Message(BaseModel):
    """消息数据模型"""
    message_id: str
    user_id: str
    group_id: Optional[str] = None
    content: str
    images: Optional[List[str]] = None
    mentions: Optional[List[str]] = None
    timestamp: datetime = None
    is_at: bool = False

    class Config:
        arbitrary_types_allowed = True


class ConfigUpdate(BaseModel):
    """配置更新模型"""
    openai: Optional[dict] = None
    vision: Optional[dict] = None
    bot: Optional[dict] = None
    blacklist: Optional[dict] = None
    whitelist: Optional[dict] = None
    features: Optional[dict] = None
    advanced: Optional[dict] = None


class ConfigResponse(BaseModel):
    """配置响应模型"""
    id: str = "config"
    data: dict


class BotStatus(BaseModel):
    """机器人状态模型"""
    napcat_connected: bool = False
    last_update: datetime = None
    recent_messages: Optional[List[Message]] = None
    error_logs: Optional[List[str]] = None

    class Config:
        arbitrary_types_allowed = True


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    baseurl: str
    apikey: str
    model: str


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    message: str
