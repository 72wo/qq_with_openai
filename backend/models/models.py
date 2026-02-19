from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
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


# ── 类型化嵌套模型（Phase 3 验证强化）──────────────────────


def _reject_null_bytes(v: str) -> str:
    if "\x00" in v:
        raise ValueError("字符串不得包含空字节")
    return v


class OpenAIConfigUpdate(BaseModel):
    baseurl: Optional[str] = Field(default=None, max_length=500)
    apikey: Optional[str] = Field(default=None, max_length=500)
    model: Optional[str] = Field(default=None, max_length=200)

    @field_validator("baseurl", "apikey", "model", mode="before")
    @classmethod
    def check_null_bytes(cls, v):
        if isinstance(v, str):
            return _reject_null_bytes(v)
        return v


class VisionConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    use_reply_config: Optional[bool] = None
    baseurl: Optional[str] = Field(default=None, max_length=500)
    apikey: Optional[str] = Field(default=None, max_length=500)
    model: Optional[str] = Field(default=None, max_length=200)

    @field_validator("baseurl", "apikey", "model", mode="before")
    @classmethod
    def check_null_bytes(cls, v):
        if isinstance(v, str):
            return _reject_null_bytes(v)
        return v


class BotConfigUpdate(BaseModel):
    prompt: Optional[str] = Field(default=None, max_length=5000)
    auto_reply: Optional[bool] = None
    group_only_at: Optional[bool] = None
    group_reply_at_all: Optional[bool] = None

    @field_validator("prompt", mode="before")
    @classmethod
    def check_null_bytes(cls, v):
        if isinstance(v, str):
            return _reject_null_bytes(v)
        return v


class ListConfigUpdate(BaseModel):
    mode: Optional[str] = Field(default=None, pattern=r"^(disabled|for_users|for_groups)$")
    users: Optional[List[str]] = Field(default=None, max_length=1000)
    groups: Optional[List[str]] = Field(default=None, max_length=1000)
    exceptions: Optional[List[str]] = Field(default=None, max_length=1000)

    @field_validator("users", "groups", "exceptions", mode="before")
    @classmethod
    def validate_id_list(cls, v):
        import re
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("必须为列表")
        for item in v:
            if not isinstance(item, str) or not re.match(r"^\d{1,15}$", item.strip()):
                raise ValueError(f"列表项必须为纯数字 ID: {item!r}")
        return [item.strip() for item in v]


class FeaturesConfigUpdate(BaseModel):
    image_processing: Optional[bool] = None
    emotion_conversion: Optional[bool] = None
    simulate_typing_enabled: Optional[bool] = None
    typing_multiplier: Optional[float] = Field(default=None, ge=0.2, le=3.0)
    typing_base_ms_per_char: Optional[int] = Field(default=None, ge=10, le=1000)
    context_enabled: Optional[bool] = None
    context_max_messages: Optional[int] = Field(default=None, ge=1, le=200)
    context_compression_enabled: Optional[bool] = None
    context_use_model_for_compression: Optional[bool] = None
    image_context_cache_size: Optional[int] = Field(default=None, ge=10, le=500)
    context_message_max_chars: Optional[int] = Field(default=None, ge=0, le=5000)
    reply_timeout_sec: Optional[int] = Field(default=None, ge=5, le=300)


class AdvancedConfigUpdate(BaseModel):
    napcat_url: Optional[str] = Field(default=None, max_length=500)
    napcat_token: Optional[str] = Field(default=None, max_length=500)
    service_port: Optional[int] = Field(default=None, ge=1024, le=65535)
    log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR"]] = None
    log_max_length: Optional[int] = Field(default=None, ge=20, le=2000)
    session_expiry_hours: Optional[int] = Field(default=None, ge=0, le=8760)
    friend_token_expiry_minutes: Optional[int] = Field(default=None, ge=1, le=1440)

    @field_validator("napcat_url", "napcat_token", mode="before")
    @classmethod
    def check_null_bytes(cls, v):
        if isinstance(v, str):
            return _reject_null_bytes(v)
        return v


class ConfigUpdate(BaseModel):
    """配置更新模型 — 类型化嵌套"""
    openai: Optional[OpenAIConfigUpdate] = None
    vision: Optional[VisionConfigUpdate] = None
    bot: Optional[BotConfigUpdate] = None
    blacklist: Optional[ListConfigUpdate] = None
    whitelist: Optional[ListConfigUpdate] = None
    features: Optional[FeaturesConfigUpdate] = None
    advanced: Optional[AdvancedConfigUpdate] = None
    proactive: Optional[dict] = None


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
    baseurl: str = Field(..., min_length=1, max_length=500)
    apikey: str = Field(..., min_length=1, max_length=500)
    model: str = Field(..., min_length=1, max_length=200)

    @field_validator("baseurl", "apikey", "model", mode="before")
    @classmethod
    def check_null_bytes(cls, v):
        if isinstance(v, str):
            return _reject_null_bytes(v)
        return v


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    message: str
