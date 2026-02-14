"""消息处理模块"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from .openai_service import OpenAIService
from .image_processor import ImageProcessor
from .emotion_converter import EmotionConverter
from ..config import Config

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器"""

    def __init__(self, config: Config, napcat_client=None):
        self.config = config
        self.napcat_client = napcat_client
        self.openai_service: Optional[OpenAIService] = None
        self.image_processor = ImageProcessor()
        self.emotion_converter = EmotionConverter()
        self._latest_seq_by_chat: Dict[str, int] = {}
        self._initialize_openai()

    def _initialize_openai(self):
        """初始化 OpenAI 服务"""
        baseurl = self.config.get("openai.baseurl", "https://api.openai.com/v1")
        apikey = self.config.get("openai.apikey")
        model = self.config.get("openai.model", "gpt-4")

        if apikey:
            self.openai_service = OpenAIService(baseurl, apikey, model)

    async def handle_message(self, message_data: Dict[str, Any]):
        """处理接收到的消息"""
        try:
            # 检查是否启用自动回复
            if not self.config.get("bot.auto_reply", True):
                return

            # 获取消息信息
            message_type = message_data.get("message_type", "")
            user_id = message_data.get("user_id")
            group_id = message_data.get("group_id")
            message_id = message_data.get("message_id")
            reply_message_id = message_data.get("reply_message_id")
            content = message_data.get("content", "")
            images = message_data.get("images", [])
            image_files = message_data.get("image_files", [])
            chat_key = message_data.get("chat_key")
            chat_seq = int(message_data.get("chat_seq", 0) or 0)

            if image_files and self.napcat_client:
                resolved_images = await self.napcat_client.resolve_image_files(image_files)
                if resolved_images:
                    images = list(dict.fromkeys(images + resolved_images))

            if chat_key and chat_seq:
                latest_seq = self._latest_seq_by_chat.get(chat_key, 0)
                if chat_seq > latest_seq:
                    self._latest_seq_by_chat[chat_key] = chat_seq

            # 群聊检查
            if message_type == "group":
                # 检查是否启用群聊仅@回复
                if self.config.get("bot.group_only_at", True):
                    if not message_data.get("is_at", False):
                        return

            # 黑白名单检查
            if not self._check_list_permission(user_id, group_id, message_type):
                logger.info(f"消息被黑白名单过滤: user={user_id}, group={group_id}")
                return

            self._append_chat_log(
                role="user",
                message_type=message_type,
                user_id=user_id,
                group_id=group_id,
                content=content,
                message_id=message_id,
            )

            quoted_message = None
            if reply_message_id and self.napcat_client:
                quoted_message = await self.napcat_client.get_message_by_id(reply_message_id)

            # 生成回复
            reply = await self._generate_reply(content, images, quoted_message)

            if reply:
                # 应用表情转义
                if self.config.get("features.emotion_conversion", True):
                    reply = self.emotion_converter.convert_emoji_to_qq(reply)

                # 发送回复
                if self.napcat_client:
                    should_quote = bool(
                        chat_key
                        and chat_seq
                        and self._latest_seq_by_chat.get(chat_key, 0) > chat_seq
                    )
                    reply_id = message_id if should_quote else None

                    if message_type == "group":
                        await self.napcat_client.send_message(
                            group_id=group_id,
                            content=reply,
                            reply_message_id=reply_id,
                        )
                    else:
                        await self.napcat_client.send_message(
                            user_id=user_id,
                            content=reply,
                            reply_message_id=reply_id,
                        )

                self._append_chat_log(
                    role="assistant",
                    message_type=message_type,
                    user_id=user_id,
                    group_id=group_id,
                    content=reply,
                    message_id=message_id,
                )
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")

    def _append_chat_log(
        self,
        role: str,
        message_type: str,
        user_id: Optional[str],
        group_id: Optional[str],
        content: str,
        message_id: Optional[str],
    ):
        from ..app import append_recent_message

        append_recent_message({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message_type": message_type,
            "user_id": str(user_id) if user_id is not None else "",
            "group_id": str(group_id) if group_id is not None else "",
            "message_id": str(message_id) if message_id is not None else "",
            "content": content or "",
        })

    def _check_list_permission(self, user_id: str, group_id: Optional[str], message_type: str) -> bool:
        """检查黑白名单权限"""
        identify = group_id if message_type == "group" else user_id

        # 检查白名单
        whitelist = self.config.get("whitelist", {})
        if whitelist.get("mode") == "disabled":
            pass  # 白名单禁用
        else:
            # 白名单启用，只允许白名单中的
            whitelist_items = whitelist.get("users" if message_type == "private" else "groups", [])
            if identify not in whitelist_items:
                return False

        # 检查黑名单
        blacklist = self.config.get("blacklist", {})
        if blacklist.get("mode") == "disabled":
            # 黑名单禁用
            return True

        blacklist_items = blacklist.get("users" if message_type == "private" else "groups", [])
        exceptions = blacklist.get("exceptions", [])

        # 如果在黑名单中但在例外列表中，允许
        if identify in blacklist_items and identify in exceptions:
            return True

        # 如果在黑名单中且不在例外中，拒绝
        if identify in blacklist_items:
            return False

        return True

    async def _generate_reply(self, message: str, images: list = None, quoted_message: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """生成 AI 回复"""
        if not self.openai_service:
            logger.error("OpenAI 服务未初始化")
            return None

        try:
            system_prompt = self.config.get("bot.prompt", "你是一个有帮助的 AI 助手")

            # 检查是否有图像并启用了图像处理
            vision_enabled = self.config.get("openai.vision_enabled", False)
            image_analysis = None
            quoted_image_analysis = None

            if images and vision_enabled:
                image_analysis = await self._analyze_images(images, system_prompt)

            quoted_text = ""
            quoted_images = []
            if quoted_message:
                quoted_text = quoted_message.get("content", "") or quoted_message.get("raw_message", "")
                quoted_images = quoted_message.get("images", []) or []
                if quoted_images and vision_enabled:
                    quoted_image_analysis = await self._analyze_images(quoted_images, system_prompt)

            # 构建消息
            message_blocks = []
            if quoted_text:
                message_blocks.append(f"[用户引用消息]\n{quoted_text}")
            if quoted_image_analysis:
                message_blocks.append(f"[引用图片分析]\n{quoted_image_analysis}")
            if image_analysis:
                message_blocks.append(f"[用户本条图片分析]\n{image_analysis}")
            message_blocks.append(f"[用户消息]\n{message}")
            full_message = "\n\n".join(message_blocks)

            # 生成回复
            messages = [{"role": "user", "content": full_message}]
            reply = await self.openai_service.generate_reply(messages, system_prompt)

            return reply
        except Exception as e:
            logger.error(f"生成回复出错: {str(e)}")
            return None

    async def _analyze_images(self, images: list, system_prompt: str) -> Optional[str]:
        """分析图像"""
        if not self.openai_service:
            return None

        try:
            prepared_images = await self.image_processor.prepare_images_for_vision_api(images)

            analysis_results = []
            for img in prepared_images:
                result = await self.openai_service.analyze_image(img, "请分析这张图片", system_prompt)
                if result:
                    analysis_results.append(result)

            return " ".join(analysis_results) if analysis_results else None
        except Exception as e:
            logger.error(f"分析图像出错: {str(e)}")
            return None

    def update_config(self):
        """更新配置后重新初始化 OpenAI 服务"""
        self._initialize_openai()
