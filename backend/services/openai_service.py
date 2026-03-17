import asyncio
import logging
import aiohttp
from typing import Optional, List, Dict, Any
import json

logger = logging.getLogger(__name__)

# 可重试的瞬态异常类型
_RETRYABLE_EXCEPTIONS = (
    aiohttp.ServerDisconnectedError,
    aiohttp.ClientOSError,
    aiohttp.ClientPayloadError,
    ConnectionResetError,
    ConnectionError,
    asyncio.TimeoutError,
)

# 可重试的 HTTP 状态码（服务端临时问题）
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenAIService:
    """OpenAI API 集成服务（持久连接 + 自动重试）"""

    def __init__(self, baseurl: str, apikey: str, model: str, timeout: int = 60,
                 max_retries: int = 3):
        self.baseurl = baseurl.rstrip('/') if baseurl else "https://api.openai.com/v1"
        self.apikey = apikey
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Authorization": f"Bearer {self.apikey}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建持久化的 ClientSession（带连接池）"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=30,              # 连接池上限
                ttl_dns_cache=300,     # DNS 缓存 5 分钟
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=self._headers,
                timeout=self.timeout,
            )
        return self._session

    async def close(self):
        """关闭持久化会话，释放连接池资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request_with_retry(self, payload: dict, *,
                                  timeout_override: aiohttp.ClientTimeout = None
                                  ) -> Optional[dict]:
        """带指数退避重试的统一请求方法。

        Returns:
            成功时返回 JSON dict；不可恢复的错误返回 None。
        """
        url = f"{self.baseurl}/chat/completions"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                session = await self._get_session()
                kwargs: dict = {"json": payload}
                if timeout_override:
                    kwargs["timeout"] = timeout_override

                async with session.post(url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()

                    # 不可重试的客户端错误（如 401 / 400）直接返回
                    if response.status not in _RETRYABLE_STATUS_CODES:
                        error_text = await response.text()
                        logger.error("OpenAI API 错误: %s - %s", response.status, error_text)
                        return None

                    # 可重试的服务端错误
                    error_text = await response.text()
                    logger.warning(
                        "OpenAI API 可重试错误 (attempt %d/%d): %s - %s",
                        attempt, self.max_retries, response.status, error_text,
                    )

            except _RETRYABLE_EXCEPTIONS as e:
                last_error = e
                logger.warning(
                    "请求瞬态异常 (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )
                # 会话可能已损坏，强制重建
                await self.close()
            except Exception as e:
                # 非瞬态异常，直接放弃
                logger.error("请求不可恢复异常: %s", e)
                return None

            # 指数退避: 1s, 2s, 4s ...
            if attempt < self.max_retries:
                delay = min(2 ** (attempt - 1), 8)
                await asyncio.sleep(delay)

        logger.error(
            "请求在 %d 次重试后仍然失败，最后异常: %s",
            self.max_retries, last_error,
        )
        return None

    async def test_connection(self) -> tuple[bool, str]:
        """测试 OpenAI API 连接"""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            }
            data = await self._request_with_retry(payload)
            if data is not None:
                return True, "连接成功"
            return False, "服务器返回错误"
        except asyncio.TimeoutError:
            return False, "连接超时"
        except Exception as e:
            return False, f"连接错误: {str(e)}"

    async def generate_reply(self, messages: List[Dict[str, str]], system_prompt: str = None) -> Optional[str]:
        """生成AI回复"""
        try:
            request_messages = []
            if system_prompt:
                request_messages.append({"role": "system", "content": system_prompt})
            request_messages.extend(messages)

            payload = {
                "model": self.model,
                "messages": request_messages,
                "temperature": 0.7,
            }

            data = await self._request_with_retry(payload)
            if data:
                return data['choices'][0]['message']['content'].strip()
            return None
        except Exception as e:
            logger.error("生成回复错误: %s", e)
            return None

    async def analyze_image(self, image_data: str, prompt: str = None, system_prompt: str = None) -> Optional[str]:
        """分析图像，极简模式。"""
        try:
            image_url = image_data if image_data.startswith("http") or image_data.startswith("data:image/") else f"data:image/jpeg;base64,{image_data}"
            text_prompt = prompt or "描述图片,20字以内"

            messages: List[Dict[str, Any]] = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
            }]

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 50,
                "temperature": 0.3,
            }

            vision_timeout = aiohttp.ClientTimeout(total=20)
            data = await self._request_with_retry(payload, timeout_override=vision_timeout)
            if data:
                return data['choices'][0]['message']['content'].strip()[:40]
            return None
        except Exception as e:
            logger.error("分析图像错误: %s", e)
            return None
