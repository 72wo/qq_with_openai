"""napcat WebSocket 客户端"""

import asyncio
import json
import re
import html
import websockets
from typing import Optional, Callable, Dict, Any
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from itertools import count
import logging

from .face_config import get_face_name

logger = logging.getLogger(__name__)


class NapcatClient:
    """napcat WebSocket 客户端"""

    def __init__(self, ws_url: str = "ws://localhost:8080/ws/napcat", token: Optional[str] = None, config=None):
        self.ws_url = ws_url
        self.token = token
        self.config = config
        self.websocket = None
        self.is_connected = False
        self.connection_mode = "forward"
        self.last_error: Optional[str] = None
        self.message_handler: Optional[Callable] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5
        self._echo_counter = count(1)
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._message_tasks: set[asyncio.Task] = set()
        self._chat_seq_map: Dict[str, int] = {}

    async def connect(self):
        """连接到 napcat"""
        try:
            ws_url, headers = self._build_connect_options()
            try:
                self.websocket = await websockets.connect(ws_url, additional_headers=headers)
            except TypeError:
                self.websocket = await websockets.connect(ws_url, extra_headers=headers)
            self.is_connected = True
            self.last_error = None
            self.reconnect_attempts = 0
            logger.info(f"成功连接到 napcat: {ws_url}")
            return True
        except Exception as e:
            error_message = str(e)
            if "[Errno 111]" in error_message or "Connection refused" in error_message:
                error_message = f"{error_message}（请确认 NapCat 已启动并开启 WebSocket 服务）"
            self.last_error = error_message
            logger.error(f"连接 napcat 失败: {error_message}")
            return False

    def _build_connect_options(self) -> tuple[str, Dict[str, str]]:
        """构建连接 URL 与认证头"""
        if not self.token:
            return self.ws_url, {}

        parsed = urlparse(self.ws_url)
        query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_items["access_token"] = self.token
        encoded_query = urlencode(query_items, doseq=True)
        ws_url_with_token = urlunparse(parsed._replace(query=encoded_query))

        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        return ws_url_with_token, headers

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            close_method = getattr(self.websocket, "close", None)
            if close_method:
                await close_method()
            self.is_connected = False
            self.websocket = None
            logger.info("已断开 napcat 连接")

    def attach_external_websocket(self, websocket: Any):
        """附加反向 WS 连接（NapCat 作为客户端）"""
        self.websocket = websocket
        self.is_connected = True
        self.connection_mode = "reverse"
        self.last_error = None
        self.reconnect_attempts = 0
        logger.info("已接入 napcat 反向 WebSocket 连接")

    def mark_external_disconnected(self):
        """标记反向 WS 已断开"""
        self.websocket = None
        self.is_connected = False
        self.last_error = "反向 WebSocket 连接已断开"

    async def send_message(
        self,
        group_id: Optional[str] = None,
        user_id: Optional[str] = None,
        content: str = "",
        images: Optional[list] = None,
        reply_message_id: Optional[str] = None,
    ):
        """发送消息"""
        if not self.is_connected:
            logger.error("未连接到 napcat")
            return False

        try:
            message_segments = []
            if reply_message_id:
                message_segments.append({
                    "type": "reply",
                    "data": {"id": str(reply_message_id)}
                })
            message_segments.append({
                "type": "text",
                "data": {"text": content}
            })

            params: Dict[str, Any] = {
                "message": message_segments,
            }

            if group_id:
                action = "send_group_msg"
                params["group_id"] = int(group_id) if str(group_id).isdigit() else group_id
            elif user_id:
                action = "send_private_msg"
                params["user_id"] = int(user_id) if str(user_id).isdigit() else user_id
            else:
                logger.error("发送消息失败: 必须提供 group_id 或 user_id")
                return False

            if images:
                params["images"] = images

            response = await self.call_action(action, params=params, timeout=8)
            if response and response.get("status") not in {"ok", "async"}:
                logger.error(f"发送消息失败: {response}")
                return False

            logger.info(f"消息已发送: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            return False

    async def call_action(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: int = 8) -> Optional[Dict[str, Any]]:
        """调用 OneBot action 并等待回执"""
        if not self.is_connected:
            logger.error("未连接到 napcat")
            return None

        params = params or {}
        echo = f"action-{next(self._echo_counter)}"
        message: Dict[str, Any] = {
            "action": action,
            "params": params,
            "echo": echo,
        }

        request_future = asyncio.get_running_loop().create_future()
        self._pending_requests[echo] = request_future

        try:
            payload = json.dumps(message)
            send_text = getattr(self.websocket, "send_text", None)
            send_method = getattr(self.websocket, "send", None)
            if send_text:
                await send_text(payload)
            elif send_method:
                await send_method(payload)
            else:
                raise RuntimeError("当前 WebSocket 对象不支持发送")

            try:
                return await asyncio.wait_for(request_future, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Action {action} 未收到回执")
                return None
        finally:
            self._pending_requests.pop(echo, None)

    async def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """通过 message_id 获取消息详情（用于引用消息）"""
        if not message_id:
            return None

        response = await self.call_action("get_msg", params={"message_id": int(message_id) if str(message_id).isdigit() else message_id})
        if not response or response.get("status") not in {"ok", "async"}:
            return None

        data = response.get("data") or {}
        message = data.get("message")
        raw_message = data.get("raw_message", "")

        images = self._extract_images_from_message(message, raw_message) if message is not None else []
        image_files = self._extract_image_files_from_message(message, raw_message)
        if image_files:
            extra_images = await self.resolve_image_files(image_files)
            for image in extra_images:
                if image not in images:
                    images.append(image)
        content = self._extract_text_from_message(message, raw_message)
        if not content:
            content = self._convert_cq_faces_in_text(raw_message)

        return {
            "message_id": str(data.get("message_id", message_id)),
            "content": content or "",
            "images": images,
            "raw_message": raw_message,
        }

    async def listen(self):
        """监听消息"""
        if not self.is_connected:
            if not await self.connect():
                return

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_payload(data)
                except json.JSONDecodeError:
                    logger.error(f"无法解析消息: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket 连接已关闭")
            self.is_connected = False
            self.last_error = "WebSocket 连接已关闭"
            await self._try_reconnect()
        except Exception as e:
            logger.error(f"监听消息出错: {str(e)}")
            self.is_connected = False
            self.last_error = str(e)

    async def _handle_payload(self, data: Dict[str, Any]):
        """处理接收到的 payload（事件/动作回执）"""
        try:
            echo = data.get("echo")
            if echo and echo in self._pending_requests:
                pending = self._pending_requests.get(echo)
                if pending and not pending.done():
                    pending.set_result(data)
                return

            if data.get("meta_event_type") == "heartbeat":
                # 心跳，不处理
                return

            if data.get("post_type") == "message":
                message_type = data.get("message_type")
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                raw_message = data.get("raw_message", "")
                message_segments = data.get("message")
                # 从事件中提取发送者昵称（OneBot v11 sender 字段）
                sender = data.get("sender", {})
                # 群名片(card) 优先，其次是 nickname
                sender_nickname = (sender.get("card") or sender.get("nickname") or "").strip()
                chat_key = f"group:{group_id}" if message_type == "group" else f"private:{user_id}"
                current_seq = self._chat_seq_map.get(chat_key, 0) + 1
                self._chat_seq_map[chat_key] = current_seq

                images = self._extract_images_from_message(message_segments, raw_message)
                image_files = self._extract_image_files_from_message(message_segments, raw_message)

                # 检测是否被 @（OneBot v11 标准：检查消息段中的 at 类型）
                self_id = str(data.get("self_id", ""))
                is_at, is_at_all = self._check_is_at(message_segments, raw_message, self_id)

                if message_type == "group":
                    logger.info(
                        f"@检测: self_id={self_id!r}, is_at={is_at}, is_at_all={is_at_all}, "
                        f"user_id={user_id}, raw={raw_message[:150]!r}, "
                        f"segments_types={[s.get('type') for s in (message_segments or []) if isinstance(s, dict)]}, "
                        f"at_qqs={[str(s.get('data',{}).get('qq','')) for s in (message_segments or []) if isinstance(s,dict) and s.get('type')=='at']}"
                    )

                # 提取纯文本内容（去掉图片/回复/at等CQ码）
                text_content = self._extract_text_from_message(message_segments, raw_message)
                if not text_content:
                    # fallback：用表情转换处理 raw_message，但也要清除图片/回复/at CQ码
                    fallback = self._convert_cq_faces_in_text(raw_message)
                    fallback = re.sub(r"\[CQ:image,[^\]]+\]", "", fallback)
                    fallback = re.sub(r"\[CQ:reply,[^\]]+\]", "", fallback)
                    fallback = re.sub(r"\[CQ:at,[^\]]+\]", "", fallback)
                    text_content = fallback.strip()

                message_data = {
                    "message_id": data.get("message_id"),
                    "user_id": user_id,
                    "group_id": group_id,
                    "sender_nickname": sender_nickname,
                    "content": text_content,
                    "raw_message": raw_message,
                    "message_type": message_type,  # "private" 或 "group"
                    "is_at": is_at,
                    "is_at_all": is_at_all,
                    "reply_message_id": self._extract_reply_message_id(message_segments, raw_message),
                    "chat_key": chat_key,
                    "chat_seq": current_seq,
                    "images": images,
                    "image_files": image_files,
                }

                if self.message_handler:
                    task = asyncio.create_task(self.message_handler(message_data))
                    self._message_tasks.add(task)
                    task.add_done_callback(self._message_tasks.discard)
        except Exception as e:
            logger.error(f"处理 payload 出错: {str(e)}")

    def _check_is_at(self, message_data: Any, raw_message: str, self_id: str) -> tuple[bool, bool]:
        """检测消息中是否 @ 了机器人（OneBot v11 标准）

        Returns:
            (is_at, is_at_all):
              is_at     — 是否直接 @ 了机器人 (data.qq == self_id)
              is_at_all — 是否 @所有人 (data.qq == "all")
        """
        is_at = False
        is_at_all = False
        try:
            if isinstance(message_data, list):
                for item in message_data:
                    if isinstance(item, dict) and item.get("type") == "at":
                        qq = str(item.get("data", {}).get("qq", ""))
                        if qq == self_id:
                            is_at = True
                        elif qq == "all":
                            is_at_all = True

            if raw_message and self_id:
                if f"[CQ:at,qq={self_id}]" in raw_message:
                    is_at = True
            if raw_message and "[CQ:at,qq=all]" in raw_message:
                is_at_all = True
        except Exception:
            pass
        return is_at, is_at_all

    def _extract_images_from_message(self, message_data: Any, raw_message: str = "") -> list:
        """从消息中提取图像"""
        images = []
        try:
            if isinstance(message_data, list):
                for item in message_data:
                    if isinstance(item, dict):
                        if item.get("type") == "image":
                            url = item.get("data", {}).get("url")
                            if url:
                                images.append(html.unescape(url))
            elif isinstance(message_data, dict):
                if message_data.get("type") == "image":
                    url = message_data.get("data", {}).get("url")
                    if url:
                        images.append(html.unescape(url))
            elif isinstance(message_data, str):
                images.extend(self._extract_image_urls_from_cq_text(message_data))

            if raw_message:
                images.extend(self._extract_image_urls_from_cq_text(raw_message))
        except Exception as e:
            logger.error(f"提取图像出错: {str(e)}")

        dedup_images = []
        seen = set()
        for image in images:
            if not image or image in seen:
                continue
            seen.add(image)
            dedup_images.append(image)
        return dedup_images

    def _extract_image_files_from_message(self, message_data: Any, raw_message: str = "") -> list[str]:
        """提取图片 file 标识，用于 get_image"""
        files: list[str] = []
        try:
            if isinstance(message_data, list):
                for item in message_data:
                    if isinstance(item, dict) and item.get("type") == "image":
                        file_id = item.get("data", {}).get("file")
                        if file_id:
                            files.append(str(file_id))
            elif isinstance(message_data, dict):
                if message_data.get("type") == "image":
                    file_id = message_data.get("data", {}).get("file")
                    if file_id:
                        files.append(str(file_id))

            text = ""
            if isinstance(message_data, str):
                text += message_data
            if raw_message:
                text += "\n" + raw_message
            if text:
                files.extend(self._extract_image_files_from_cq_text(text))
        except Exception:
            return []

        dedup_files = []
        seen = set()
        for file_id in files:
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            dedup_files.append(file_id)
        return dedup_files

    async def resolve_image_files(self, image_files: list[str]) -> list[str]:
        """通过 get_image 解析 file 标识，返回可读取路径"""
        resolved: list[str] = []
        for file_id in image_files:
            response = await self.call_action("get_image", params={"file": file_id}, timeout=8)
            if not response or response.get("status") not in {"ok", "async"}:
                continue
            data = response.get("data") or {}
            for key in ("file", "path", "url"):
                value = data.get(key)
                if value:
                    resolved.append(str(value))
                    break
        return resolved

    def _extract_image_urls_from_cq_text(self, text: str) -> list[str]:
        urls: list[str] = []
        if not text:
            return urls
        pattern = re.compile(r"\[CQ:image,([^\]]+)\]")
        for match in pattern.findall(text):
            attrs = self._parse_cq_attrs(match)
            url = attrs.get("url")
            if url:
                urls.append(html.unescape(url))
        return urls

    def _extract_image_files_from_cq_text(self, text: str) -> list[str]:
        files: list[str] = []
        if not text:
            return files
        pattern = re.compile(r"\[CQ:image,([^\]]+)\]")
        for match in pattern.findall(text):
            attrs = self._parse_cq_attrs(match)
            file_id = attrs.get("file")
            if file_id:
                files.append(file_id)
        return files

    def _parse_cq_attrs(self, attr_text: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for part in attr_text.split(","):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            attrs[key.strip()] = value.strip()
        return attrs

    def _face_id_to_text(self, face_id: int) -> str:
        """将表情ID转换为文字描述"""
        name = get_face_name(face_id)
        return f"[{name}]"

    def _convert_cq_faces_in_text(self, text: str) -> str:
        """转换CQ码中的表情为文字描述"""
        # 检查是否启用表情转换
        if self.config and not self.config.get("features.emotion_conversion", True):
            return text
        
        # 处理普通表情 [CQ:face,id=xxx]
        def replace_face(match):
            try:
                face_id = int(match.group(1))
                return self._face_id_to_text(face_id)
            except:
                return "[表情]"
        text = re.sub(r"\[CQ:face,id=(\d+)[^\]]*\]", replace_face, text)
        
        # 处理超级表情/魔法表情 [CQ:mface,...]
        def replace_mface(match):
            attrs = self._parse_cq_attrs(match.group(1))
            # 尝试获取summary或者text属性作为表情描述
            summary = attrs.get("summary", "") or attrs.get("text", "")
            if summary:
                return f"[{summary}]"
            return "[超级表情]"
        text = re.sub(r"\[CQ:mface,([^\]]+)\]", replace_mface, text)
        
        # 处理戳一戳 [CQ:poke,...]
        text = re.sub(r"\[CQ:poke[^\]]*\]", "[戳一戳]", text)
        
        # 处理骰子 [CQ:dice]
        text = re.sub(r"\[CQ:dice[^\]]*\]", "[骰子]", text)
        
        # 处理猜拳 [CQ:rps]
        text = re.sub(r"\[CQ:rps[^\]]*\]", "[猜拳]", text)
        
        return text

    def convert_text_faces_to_cq(self, text: str) -> str:
        """把像 `[微笑]` 或 `:微笑:` 这类基于名称的表情，转换为 CQ face（如果能匹配到 ID）。

        - 保持已有 CQ 码不变。
        - 只替换能在 `face_config` 中找到名称的项。
        """
        if not text:
            return text

        # 避免重复转换已经是 CQ 的片段
        if "[CQ:" in text:
            # 只处理非 CQ 段：先把 CQ 段剥离，替换后再还原
            parts = re.split(r'(\[CQ:[^\]]+\])', text)
            out_parts = []
            from .face_config import get_face_id_by_name
            for p in parts:
                if p.startswith('[CQ:'):
                    out_parts.append(p)
                else:
                    # 替换 [名称] 形式
                    def repl_bracket(m):
                        name = m.group(1)
                        fid = get_face_id_by_name(name)
                        return f"[CQ:face,id={fid}]" if fid is not None else m.group(0)
                    s = re.sub(r"\[([^\]]+)\]", repl_bracket, p)
                    # 替换 :名称: 形式
                    def repl_colon(m):
                        name = m.group(1)
                        fid = get_face_id_by_name(name)
                        return f"[CQ:face,id={fid}]" if fid is not None else m.group(0)
                    s = re.sub(r":([^:\s]+):", repl_colon, s)
                    out_parts.append(s)
            return ''.join(out_parts)

        # 没有 CQ 码的简单文本直接替换
        from .face_config import get_face_id_by_name
        def repl_bracket_simple(m):
            name = m.group(1)
            fid = get_face_id_by_name(name)
            return f"[CQ:face,id={fid}]" if fid is not None else m.group(0)
        text = re.sub(r"\[([^\]]+)\]", repl_bracket_simple, text)
        def repl_colon_simple(m):
            name = m.group(1)
            fid = get_face_id_by_name(name)
            return f"[CQ:face,id={fid}]" if fid is not None else m.group(0)
        text = re.sub(r":([^:\s]+):", repl_colon_simple, text)
        return text

    def _extract_text_from_message(self, message_data: Any, raw_message: str = "") -> str:
        """从消息段中提取纯文本（包括表情转义）"""
        # 如果有raw_message，直接处理CQ码
        if raw_message:
            text = raw_message
            # 移除图片和回复CQ码
            text = re.sub(r"\[CQ:image,[^\]]+\]", "", text)
            text = re.sub(r"\[CQ:reply,[^\]]+\]", "", text)
            text = re.sub(r"\[CQ:at,[^\]]+\]", "", text)
            # 转换表情
            text = self._convert_cq_faces_in_text(text)
            # 处理HTML实体
            text = html.unescape(text)
            return text.strip()
        
        if isinstance(message_data, str):
            return self._convert_cq_faces_in_text(message_data)

        if isinstance(message_data, list):
            texts = []
            for item in message_data:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                data = item.get("data", {})
                
                if item_type == "text":
                    texts.append(data.get("text", ""))
                elif item_type == "face":
                    # 普通QQ表情
                    if self.config and self.config.get("features.emotion_conversion", True):
                        try:
                            face_id = int(data.get("id", 0))
                            texts.append(self._face_id_to_text(face_id))
                        except:
                            texts.append("[表情]")
                    else:
                        texts.append("")
                elif item_type == "mface":
                    # 超级表情/魔法表情
                    summary = data.get("summary", "") or data.get("text", "")
                    if summary:
                        texts.append(f"[{summary}]")
                    else:
                        texts.append("[超级表情]")
                elif item_type == "poke":
                    texts.append("[戳一戳]")
                elif item_type == "dice":
                    texts.append("[骰子]")
                elif item_type == "rps":
                    texts.append("[猜拳]")
            return "".join(texts).strip()

        if isinstance(message_data, dict):
            item_type = message_data.get("type")
            data = message_data.get("data", {})
            
            if item_type == "text":
                return data.get("text", "")
            elif item_type == "face":
                if self.config and self.config.get("features.emotion_conversion", True):
                    try:
                        face_id = int(data.get("id", 0))
                        return self._face_id_to_text(face_id)
                    except:
                        return "[表情]"
                else:
                    return ""
            elif item_type == "mface":
                summary = data.get("summary", "") or data.get("text", "")
                return f"[{summary}]" if summary else "[超级表情]"
        return ""

    def _extract_reply_message_id(self, message_data: Any, raw_message: str = "") -> Optional[str]:
        """提取引用消息 ID"""
        try:
            if isinstance(message_data, list):
                for item in message_data:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "reply":
                        reply_id = item.get("data", {}).get("id")
                        if reply_id is not None:
                            return str(reply_id)
            elif isinstance(message_data, dict):
                if message_data.get("type") == "reply":
                    reply_id = message_data.get("data", {}).get("id")
                    if reply_id is not None:
                        return str(reply_id)

            match = re.search(r"\[CQ:reply,id=([^\]]+)\]", raw_message or "")
            if match:
                return match.group(1)
        except Exception:
            return None
        return None

    async def _try_reconnect(self):
        """尝试重新连接"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"尝试重新连接 (第 {self.reconnect_attempts}/{self.max_reconnect_attempts} 次)...")
            await asyncio.sleep(self.reconnect_delay)

            if await self.connect():
                await self.listen()
                return

        logger.error("无法连接到 napcat，已放弃")

    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self.message_handler = handler

    async def run(self):
        """运行客户端（自动重连）"""
        while True:
            try:
                await self.listen()
            except Exception as e:
                logger.error(f"客户端运行错误: {str(e)}")
                self.is_connected = False
                self.last_error = str(e)
                await asyncio.sleep(self.reconnect_delay)
