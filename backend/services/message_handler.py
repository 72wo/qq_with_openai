"""消息处理模块"""

import asyncio
import logging
from typing import Optional, Dict, Any, Deque, List
from datetime import datetime, timedelta
from collections import deque, OrderedDict
from .openai_service import OpenAIService
from .image_processor import ImageProcessor
from ..config import Config

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器"""

    def __init__(self, config: Config, napcat_client=None):
        self.config = config
        self.napcat_client = napcat_client
        self.openai_service: Optional[OpenAIService] = None  # 回复模型
        self.vision_service: Optional[OpenAIService] = None  # 视觉模型
        self.image_processor = ImageProcessor()

        # 按 chat_key 隔离的多轮对话历史（标准 role/content 格式）
        self._chat_history: Dict[str, deque] = {}
        # per-chat 锁，保证同一会话中消息串行处理（避免乱序）
        self._chat_locks: Dict[str, asyncio.Lock] = {}
        # 图片分析缓存（LRU）
        self._image_analysis_cache: OrderedDict = OrderedDict()

        # 用于并发/序号检查
        self._latest_seq_by_chat: Dict[str, int] = {}
        self._initialize_openai()

    def _initialize_openai(self):
        """初始化 OpenAI 服务（回复模型和视觉模型）"""
        # 初始化回复模型
        baseurl = self.config.get("openai.baseurl", "https://api.openai.com/v1")
        apikey = self.config.get("openai.apikey")
        model = self.config.get("openai.model", "gpt-4")

        max_tokens = int(self.config.get("openai.max_tokens", 500) or 500)
        reply_timeout = int(self.config.get("openai.reply_timeout_sec", 60) or 60)

        if apikey:
            self.openai_service = OpenAIService(baseurl, apikey, model, max_tokens=max_tokens, timeout=reply_timeout)

        # 初始化视觉模型
        vision_enabled = self.config.get("vision.enabled", False)
        if vision_enabled:
            use_reply_config = self.config.get("vision.use_reply_config", True)
            if use_reply_config:
                # 使用回复模型的配置
                if apikey:
                    vision_model = self.config.get("vision.model", "gpt-4-vision-preview")
                    self.vision_service = OpenAIService(baseurl, apikey, vision_model)
            else:
                # 使用独立的视觉模型配置
                vision_baseurl = self.config.get("vision.baseurl", baseurl)
                vision_apikey = self.config.get("vision.apikey", apikey)
                vision_model = self.config.get("vision.model", "gpt-4-vision-preview")
                if vision_apikey:
                    self.vision_service = OpenAIService(vision_baseurl, vision_apikey, vision_model)

    async def handle_message(self, message_data: Dict[str, Any]):
        """处理接收到的消息。按 chat_key 加锁保证同一会话串行处理。"""
        try:
            if not self.config.get("bot.auto_reply", True):
                return

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
            sender_nickname = message_data.get("sender_nickname", "")
            is_at = message_data.get("is_at", False)
            is_at_all = message_data.get("is_at_all", False)

            # 检查是否启用图像处理（视觉模型未启用时强制关闭）
            vision_enabled = self.config.get("vision.enabled", False)
            image_processing = self.config.get("features.image_processing", True)
            if not vision_enabled or not image_processing:
                # 图像处理不生效时，检查是否为纯图片消息
                has_images = bool(images or image_files)
                if has_images and not content.strip():
                    # 纯图片消息，直接忽略不回复
                    logger.debug(f"图像处理未启用，忽略纯图片消息: user={user_id}, group={group_id}")
                    return
                # 非纯图片消息，清除图片数据但仍处理文本
                images = []
                image_files = []

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
                if not self.config.get("bot.group_only_at", True):
                    # 群聊仅@时回复 关闭 → 群聊不回复任何消息
                    logger.debug(f"群聊回复已关闭，跳过: group={group_id}, user={user_id}")
                    return
                # 群聊仅@时回复 开启 → 检查是否被直接@或引用了消息
                has_reply = bool(reply_message_id)
                if not is_at and not has_reply:
                    # 未被直接@也没有引用消息，检查是否@所有人且配置允许
                    if is_at_all and self.config.get("bot.group_reply_at_all", False):
                        pass  # @所有人且允许回复，放行
                    else:
                        logger.debug(f"群聊未被@且无引用，跳过: group={group_id}, user={user_id}")
                        return

            # 黑白名单检查
            if not self._check_list_permission(user_id, group_id, message_type):
                logger.info(f"消息被黑白名单过滤: user={user_id}, group={group_id}")
                return

            # 异步记录日志
            asyncio.create_task(self._append_chat_log_async(
                role="user", message_type=message_type, user_id=user_id,
                group_id=group_id, content=content, message_id=message_id,
            ))

            # === 获取 per-chat 锁，保证同一会话的消息串行处理 ===
            if chat_key not in self._chat_locks:
                self._chat_locks[chat_key] = asyncio.Lock()
            
            async with self._chat_locks[chat_key]:
                # 获取引用消息
                quoted_message = None
                if reply_message_id and self.napcat_client:
                    quoted_message = await self.napcat_client.get_message_by_id(reply_message_id)

                # 构建当前用户消息内容（含图片描述、引用和@上下文）
                user_content = await self._build_user_content(
                    content, images, quoted_message,
                    is_at=is_at, is_at_all=is_at_all,
                    sender_nickname=sender_nickname,
                    message_type=message_type,
                )

                # 写入对话历史
                self._append_to_history(chat_key, "user", user_content)

                # 生成回复（直接发送完整对话历史）
                reply = await self._generate_reply(chat_key)

                if reply:
                    # 写入 assistant 回复到对话历史
                    self._append_to_history(chat_key, "assistant", reply)


                    # 模拟打字
                    simulate_typing = self.config.get("features.simulate_typing_enabled", False)
                    if simulate_typing:
                        received_ts = datetime.now()
                        simulated_time = self._calculate_simulated_response_time(
                            content, images, quoted_message, reply
                        )
                        actual_elapsed = (datetime.now() - received_ts).total_seconds()
                        wait_time = max(0.0, simulated_time - actual_elapsed)
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)

                    # 发送回复
                    if self.napcat_client:
                        should_quote = bool(
                            chat_key and chat_seq
                            and self._latest_seq_by_chat.get(chat_key, 0) > chat_seq
                        )
                        reply_id = message_id if should_quote else None

                        if message_type == "group":
                            await self.napcat_client.send_message(
                                group_id=group_id, content=reply, reply_message_id=reply_id,
                            )
                        else:
                            await self.napcat_client.send_message(
                                user_id=user_id, content=reply, reply_message_id=reply_id,
                            )

                    # 异步记录日志
                    asyncio.create_task(self._append_chat_log_async(
                        role="assistant", message_type=message_type, user_id=user_id,
                        group_id=group_id, content=reply, message_id=message_id,
                    ))
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
        """同步记录聊天日志"""
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

    async def _append_chat_log_async(
        self,
        role: str,
        message_type: str,
        user_id: Optional[str],
        group_id: Optional[str],
        content: str,
        message_id: Optional[str],
    ):
        """异步记录聊天日志（不阻塞主流程）"""
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
        """检查黑白名单权限

        前端模式:
          - disabled   : 不启用
          - for_users  : 按用户 ID 过滤（所有消息类型均检查 user_id）
          - for_groups : 按群组 ID 过滤（仅群消息检查 group_id，私聊放行）
        """
        user_id_str = str(user_id) if user_id else ""
        group_id_str = str(group_id) if group_id else ""

        # --- 黑白名单互斥：只有一个会生效 ---
        whitelist = self.config.get("whitelist", {})
        wl_mode = whitelist.get("mode", "disabled")
        blacklist = self.config.get("blacklist", {})
        bl_mode = blacklist.get("mode", "disabled")

        # 白名单优先：如果白名单启用，黑名单无效
        if wl_mode != "disabled":
            if wl_mode == "for_users":
                return user_id_str in whitelist.get("users", [])
            elif wl_mode == "for_groups":
                if message_type == "group":
                    return group_id_str in whitelist.get("groups", [])
                # 私聊在群聊白名单模式下放行
                return True
            return True

        # 黑名单检查
        if bl_mode == "disabled":
            return True

        exceptions = blacklist.get("exceptions", [])
        if bl_mode == "for_users":
            if user_id_str in blacklist.get("users", []):
                return user_id_str in exceptions
        elif bl_mode == "for_groups":
            if message_type == "group" and group_id_str in blacklist.get("groups", []):
                return group_id_str in exceptions

        return True

    async def _build_user_content(
        self,
        message: str,
        images: list,
        quoted_message: Optional[Dict[str, Any]],
        is_at: bool = False,
        is_at_all: bool = False,
        sender_nickname: str = "",
        message_type: str = "",
    ) -> str:
        """构建单条 user 消息内容，将引用、图片描述和 @上下文拼入文本。"""
        parts = []

        # 群聊 @ 上下文（告诉 AI 是谁 @ 了它）
        if message_type == "group":
            name = sender_nickname or "someone"
            if is_at:
                parts.append(f"[用户 {name} @了你]")
            elif is_at_all:
                parts.append(f"[你被 @全体成员 提及，发送者是 {name}]")

        # 引用消息（文本 + 图片）
        if quoted_message:
            qt = (quoted_message.get("content") or quoted_message.get("raw_message") or "")[:100]
            if qt:
                parts.append(f"[引用]{qt}")
            # 处理引用消息中的图片（与私聊逻辑一致）
            quoted_images = quoted_message.get("images", [])
            if quoted_images and self.config.get("vision.enabled", False):
                system_prompt = self.config.get("bot.prompt", "")
                quoted_img_desc = await self._analyze_images(quoted_images, system_prompt)
                if quoted_img_desc:
                    parts.append(f"[引用图片]{quoted_img_desc}")

        # 图片分析 - 仅在视觉模型启用时处理
        # 如果视觉模型未启用，完全忽略图片（不解析也不回复）
        if images and self.config.get("vision.enabled", False):
            system_prompt = self.config.get("bot.prompt", "")
            img_desc = await self._analyze_images(images, system_prompt)
            if img_desc:
                parts.append(f"[图片]{img_desc}")

        # 当前消息文本
        if message:
            parts.append(message)

        return "\n".join(parts)

    def _append_to_history(self, chat_key: Optional[str], role: str, content: str):
        """向对话历史追加一条消息。

        一轮对话 = 一条 user 消息 + 紧随其后的 assistant 回复。
        context_max_messages 只计算 user 消息数量。
        超出时按整轮（user + assistant）淘汰最旧的对话。
        如果启用了上下文压缩，被淘汰的轮次会被压缩为摘要保留在
        历史最前面，而不是直接丢弃。
        """
        if not chat_key or not content:
            return

        if chat_key not in self._chat_history:
            self._chat_history[chat_key] = deque()
        self._chat_history[chat_key].append({"role": role, "content": content})

        # 按 user 消息轮数淘汰
        max_user_messages = max(1, int(self.config.get("features.context_max_messages", 8) or 8))
        compression_enabled = self.config.get("features.context_compression_enabled", False)

        while self._count_user_messages(chat_key) > max_user_messages:
            # 取出最旧的一整轮对话（user + 紧随的 assistant）
            evicted_round = self._pop_oldest_round(chat_key)
            if not evicted_round:
                break

            # 如果启用压缩，将被淘汰的轮次压缩为摘要
            if compression_enabled and evicted_round:
                self._compress_round_into_summary(chat_key, evicted_round)

    def _count_user_messages(self, chat_key: str) -> int:
        """统计指定会话中 user 消息的数量（不含 system/summary）。"""
        if chat_key not in self._chat_history:
            return 0
        return sum(1 for m in self._chat_history[chat_key] if m["role"] == "user")

    def _pop_oldest_round(self, chat_key: str) -> List[Dict[str, str]]:
        """移除并返回最旧的一轮对话（user + 紧随的 assistant）。

        会跳过开头的 system 消息（压缩摘要），只移除第一个
        user 及其紧随的 assistant。
        """
        history = self._chat_history.get(chat_key)
        if not history:
            return []

        evicted = []
        # 跳过开头的 system 消息（压缩摘要）
        while history and history[0]["role"] == "system":
            # system 消息保留在原位，不移除
            break

        # 找到第一条 user 消息并移除
        # 先移除 user 之前可能残留的孤立 assistant
        while history and history[0]["role"] not in ("user", "system"):
            evicted.append(history.popleft())

        # 移除 user 消息
        if history and history[0]["role"] == "user":
            evicted.append(history.popleft())

        # 移除紧随的 assistant 消息
        if history and history[0]["role"] == "assistant":
            evicted.append(history.popleft())

        return evicted

    def _compress_round_into_summary(self, chat_key: str, evicted_round: List[Dict[str, str]]):
        """将被淘汰的一轮对话压缩为摘要，插入历史最前面作为 system 消息。"""
        if not evicted_round:
            return

        # 提取对话内容
        user_part = ""
        assistant_part = ""
        for msg in evicted_round:
            if msg["role"] == "user":
                user_part = msg["content"]
            elif msg["role"] == "assistant":
                assistant_part = msg["content"]

        # 简单截断式压缩（不调用模型）
        max_summary_len = 60
        user_summary = user_part[:max_summary_len] + ("…" if len(user_part) > max_summary_len else "")
        assistant_summary = assistant_part[:max_summary_len] + ("…" if len(assistant_part) > max_summary_len else "")
        summary = f"[历史摘要] 用户:{user_summary} → AI:{assistant_summary}"

        history = self._chat_history[chat_key]
        # 查找是否已有摘要（第一条 system 消息）
        if history and history[0]["role"] == "system":
            # 合并到已有摘要
            existing = history[0]["content"]
            # 限制摘要总长度，避免无限增长
            max_total_summary = 500
            combined = existing + "\n" + summary
            if len(combined) > max_total_summary:
                # 截断保留最新的部分
                combined = combined[-max_total_summary:]
            history[0]["content"] = combined
        else:
            # 创建新的摘要消息，插入最前面
            history.appendleft({"role": "system", "content": summary})

    async def _generate_reply(self, chat_key: Optional[str]) -> Optional[str]:
        """生成AI回复。直接发送标准多轮 messages 数组，由 API 自身处理记忆。"""
        if not self.openai_service:
            logger.error("OpenAI 服务未初始化")
            return None

        try:
            base_prompt = self.config.get("bot.prompt", "你是一个有帮助的 AI 助手")
            # 添加回复长度建议
            suggested_len = int(self.config.get("features.context_message_max_chars", 0) or 0)
            if suggested_len > 0:
                system_prompt = base_prompt + f"\n请将回复控制在约{suggested_len}个字符左右。"
            else:
                system_prompt = base_prompt

            # 检查是否启用上下文
            context_enabled = self.config.get("features.context_enabled", True)
            
            # 构建 messages：从对话历史直接取（已经是标准 role/content 格式）
            messages = []
            if context_enabled and chat_key and chat_key in self._chat_history:
                messages = list(self._chat_history[chat_key])
            
            if not messages:
                return None

            # 获取配置的平均回复长度（作为max_tokens）
            avg_length = int(self.config.get("openai.reply_avg_length", 50) or 50)
            
            return await self.openai_service.generate_reply(messages, system_prompt, max_tokens=avg_length)
        except Exception as e:
            logger.error(f"生成回复出错: {str(e)}")
            return None

    async def _analyze_images(self, images: list, system_prompt: str = None) -> Optional[str]:
        """分析图像，极简模式，最大限度减少token消耗。"""
        if not self.vision_service:
            return None

        try:
            prepared_images = await self.image_processor.prepare_images_for_vision_api(images)
            if not prepared_images:
                return None
            
            # 只分析第一张图片（减少API调用）
            img = prepared_images[0]
            
            # 检查缓存
            cached = self._image_analysis_cache.get(img)
            if cached:
                return cached

            # 极简提示词
            result = await self.vision_service.analyze_image(img, "描述图片,20字以内", None)
            if result:
                result = result[:40]  # 限制40字符
                self._image_analysis_cache[img] = result
                # LRU控制
                while len(self._image_analysis_cache) > 32:
                    self._image_analysis_cache.popitem(last=False)
                return result
            return None
        except Exception as e:
            logger.error(f"分析图像出错: {str(e)}")
            return None

    def _estimate_typing_length(self, text: str) -> int:
        """估算用于打字模拟的字符数（去掉 CQ 码与图片标签）。"""
        if not text:
            return 0
        # 去除 CQ 码与方括号表情
        import re
        s = re.sub(r"\[CQ:[^\]]+\]", '', text)
        s = re.sub(r"\[[^\]]+\]", '', s)
        s = re.sub(r"\<img[^\>]*\>", '', s)
        return max(1, len(s.strip()))

    def _calculate_simulated_response_time(
        self,
        user_message: str,
        images: list,
        quoted_message: Optional[Dict[str, Any]],
        ai_reply: str
    ) -> float:
        """计算模拟的回复总时间（思考时间 + 打字时间）

        真实人类回复流程：
        1. 阅读理解消息（0.5-2秒）
        2. 思考组织回复（1-5秒，复杂问题更长）
        3. 打字输出（每字0.05-0.15秒）

        Args:
            user_message: 用户消息内容
            images: 用户发送的图片列表
            quoted_message: 引用的消息
            ai_reply: AI 生成的回复

        Returns:
            模拟的总时间（秒）
        """
        import random

        # 获取配置参数
        typing_multiplier = float(self.config.get("features.typing_multiplier", 1.0) or 1.0)
        base_ms_per_char = int(self.config.get("features.typing_base_ms_per_char", 120) or 120)

        # 1. 阅读理解时间（0.5-2秒）
        # 消息越长，阅读时间越长
        reading_time = 0.5 + min(1.5, len(user_message) / 200)
        # 有图片需要额外时间
        if images:
            reading_time += 0.5 * len(images)
        # 有引用消息需要额外时间
        if quoted_message:
            reading_time += 0.5

        # 2. 思考时间（1-8秒）
        # 基础思考时间
        thinking_time = 1.0
        # 根据用户消息长度增加思考时间
        thinking_time += min(2.0, len(user_message) / 100)
        # 有图片需要更多思考时间
        if images:
            thinking_time += 1.0 * len(images)
        # 有引用消息需要更多思考时间
        if quoted_message:
            thinking_time += 0.5
        # AI 回复越长，说明思考越深入
        thinking_time += min(2.0, len(ai_reply) / 100)
        # 添加随机波动（±20%），让时间更自然
        thinking_time *= random.uniform(0.8, 1.2)

        # 3. 打字时间
        # 估算回复字符数（去掉 CQ 码和表情）
        reply_chars = self._estimate_typing_length(ai_reply)
        # 打字速度：每字 base_ms_per_char 毫秒，multiplier 是速度倍率（越大越快）
        typing_time = (reply_chars * base_ms_per_char / 1000.0) / typing_multiplier
        # 添加随机波动（±15%），模拟打字速度变化
        typing_time *= random.uniform(0.85, 1.15)

        # 总时间 = 阅读时间 + 思考时间 + 打字时间
        total_time = reading_time + thinking_time + typing_time

        # 确保最小时间（避免太快）
        total_time = max(2.0, total_time)

        logger.debug(
            f"模拟打字时间: 阅读={reading_time:.2f}s, 思考={thinking_time:.2f}s, "
            f"打字={typing_time:.2f}s, 总计={total_time:.2f}s"
        )

        return total_time

    def update_config(self):
        """更新配置后重新初始化 OpenAI 服务并清空对话历史"""
        self._initialize_openai()
        # 清空对话历史，确保新的配置生效
        self._chat_history.clear()
