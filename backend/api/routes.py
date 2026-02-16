"""API 路由"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
from ..models import ConfigResponse, ConfigUpdate, TestConnectionResponse
from ..services import OpenAIService, NapcatClient
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["API"])


@router.get("/config")
async def get_config() -> ConfigResponse:
    """获取配置"""
    try:
        from ..app import app_state
        config = app_state["config"]
        return ConfigResponse(data=config.get_all())
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置失败")


@router.post("/config")
async def save_config(config_update: ConfigUpdate):
    """保存配置"""
    try:
        from ..app import app_state
        config = app_state["config"]
        old_napcat_url = config.get("advanced.napcat_url", "ws://localhost:8080/ws/napcat")
        old_napcat_token = config.get("advanced.napcat_token", "")
        config_dict = config.get_all()

        # 更新配置
        if config_update.openai:
            config_dict["openai"].update(config_update.openai)
        if config_update.vision:
            config_dict["vision"].update(config_update.vision)
        if config_update.bot:
            config_dict["bot"].update(config_update.bot)
        if config_update.blacklist:
            config_dict["blacklist"].update(config_update.blacklist)
        if config_update.whitelist:
            config_dict["whitelist"].update(config_update.whitelist)
        if config_update.features:
            config_dict["features"].update(config_update.features)
        if config_update.advanced:
            config_dict["advanced"].update(config_update.advanced)

        # --- 联动约束 ---
        # 1. 视觉模型未启用时，强制关闭图像处理
        if not config_dict.get("vision", {}).get("enabled", False):
            config_dict.setdefault("features", {})["image_processing"] = False

        # 2. 黑白名单互斥：如果两个都启用，以最后提交的为准（另一个强制 disabled）
        bl_mode = config_dict.get("blacklist", {}).get("mode", "disabled")
        wl_mode = config_dict.get("whitelist", {}).get("mode", "disabled")
        if bl_mode != "disabled" and wl_mode != "disabled":
            # 两者都启用时，白名单优先，黑名单强制关闭
            config_dict["blacklist"]["mode"] = "disabled"

        config.update_config(config_dict)

        # 重新初始化 OpenAI 服务（包括视觉模型）
        message_handler = app_state.get("message_handler")
        if message_handler:
            message_handler.update_config()

        # 动态更新日志级别
        new_log_level = config.get("advanced.log_level", "INFO")
        logging.getLogger().setLevel(getattr(logging, new_log_level, logging.INFO))

        new_napcat_url = config.get("advanced.napcat_url", "ws://localhost:8080/ws/napcat")
        new_napcat_token = config.get("advanced.napcat_token", "")
        if new_napcat_url != old_napcat_url or new_napcat_token != old_napcat_token:
            old_client = app_state.get("napcat_client")
            old_task = app_state.get("napcat_task")

            if old_task:
                old_task.cancel()
            if old_client:
                await old_client.disconnect()

            app_state["napcat_client"] = NapcatClient(new_napcat_url, new_napcat_token, app_state["config"])
            app_state["message_handler"].napcat_client = app_state["napcat_client"]
            app_state["napcat_client"].set_message_handler(app_state["message_handler"].handle_message)

            # 纯服务端模式：配置更新后仅重置客户端对象，不发起主动连接
            app_state["napcat_task"] = None
            logger.info("NapCat 客户端配置已更新")

        return {"success": True, "message": "配置已保存"}
    except Exception as e:
        logger.error(f"保存配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="保存配置失败")


@router.post("/test-connection")
async def test_connection(request_data: Dict[str, Any]) -> TestConnectionResponse:
    """测试 OpenAI 连接"""
    try:
        baseurl = request_data.get("baseurl", "https://api.openai.com/v1")
        apikey = request_data.get("apikey")
        model = request_data.get("model", "gpt-4")

        if not apikey:
            return TestConnectionResponse(success=False, message="API Key 不能为空")

        openai_service = OpenAIService(baseurl, apikey, model)
        success, message = await openai_service.test_connection()

        return TestConnectionResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"测试连接失败: {str(e)}")
        return TestConnectionResponse(success=False, message=f"测试连接失败: {str(e)}")


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取机器人状态"""
    try:
        from ..app import app_state, get_recent_messages
        napcat_client = app_state.get("napcat_client")
        config = app_state.get("config")

        napcat_connected = False
        napcat_error = None
        napcat_url = ""
        if napcat_client:
            # 本项目作为 WebSocket 服务器，NapCat 作为客户端连接
            # 直接使用 is_connected 标志判断连接状态
            napcat_connected = bool(napcat_client.is_connected)
            napcat_error = getattr(napcat_client, "last_error", None)
            napcat_url = napcat_client.ws_url

        return {
            "napcat_connected": napcat_connected,
            "status": "running",
            "napcat_url": napcat_url,
            "napcat_error": napcat_error,
            "recent_messages": get_recent_messages(),
            "log_max_length": config.get("advanced.log_max_length", 200) if config else 200,
        }
    except Exception as e:
        logger.error(f"获取状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取状态失败")


@router.post("/logs/clear")
async def clear_logs() -> Dict[str, Any]:
    """清空消息日志"""
    try:
        from ..app import clear_recent_messages
        clear_recent_messages()
        return {"success": True, "message": "日志已清空"}
    except Exception as e:
        logger.error(f"清空日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="清空日志失败")
