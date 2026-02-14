import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
import json


class OpenAIService:
    """OpenAI API 集成服务"""

    def __init__(self, baseurl: str, apikey: str, model: str):
        self.baseurl = baseurl.rstrip('/') if baseurl else "https://api.openai.com/v1"
        self.apikey = apikey
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=60)

    async def test_connection(self) -> tuple[bool, str]:
        """测试 OpenAI API 连接"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.apikey}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 10
                }

                async with session.post(
                    f"{self.baseurl}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        return True, "连接成功"
                    elif response.status == 401:
                        return False, "API Key 无效"
                    else:
                        return False, f"服务器错误: {response.status}"
        except asyncio.TimeoutError:
            return False, "连接超时"
        except Exception as e:
            return False, f"连接错误: {str(e)}"

    async def generate_reply(self, messages: List[Dict[str, str]], system_prompt: str = None) -> Optional[str]:
        """生成 AI 回复"""
        try:
            request_messages = []

            if system_prompt:
                request_messages.append({"role": "system", "content": system_prompt})

            request_messages.extend(messages)

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.apikey}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": request_messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }

                async with session.post(
                    f"{self.baseurl}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                    else:
                        error_text = await response.text()
                        print(f"OpenAI API 错误: {response.status} - {error_text}")
                        return None
        except Exception as e:
            print(f"生成回复错误: {str(e)}")
            return None

    async def analyze_image(self, image_data: str, prompt: str = None, system_prompt: str = None) -> Optional[str]:
        """分析图像（Vision API）"""
        try:
            image_url = image_data if image_data.startswith("http") or image_data.startswith("data:image/") else f"data:image/jpeg;base64,{image_data}"
            text_prompt = prompt or "请分析这张图片"

            def build_messages(content: Any) -> List[Dict[str, Any]]:
                messages: List[Dict[str, Any]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": content})
                return messages

            # 兼容不同 OpenAI 网关的多种视觉 schema
            candidate_messages = [
                # OpenAI Chat Completions 标准格式
                build_messages([
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]),
                # 部分兼容网关使用 image_url 为字符串
                build_messages([
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": image_url},
                ]),
                # 某些网关要求 image_url 对象携带 type
                build_messages([
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"type": "url", "url": image_url}},
                ]),
                # 最后回退：把 URL 作为纯文本
                build_messages(f"{text_prompt}\n图片地址: {image_url}"),
            ]

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.apikey}",
                    "Content-Type": "application/json"
                }
                last_error = None

                for messages in candidate_messages:
                    payload = {
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": 500
                    }

                    async with session.post(
                        f"{self.baseurl}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data['choices'][0]['message']['content'].strip()

                        error_text = await response.text()
                        last_error = f"Vision API 错误: {response.status} - {error_text}"

                        # 非 schema 类错误直接返回（例如鉴权失败）
                        if response.status in (401, 403, 429, 500):
                            print(last_error)
                            return None

                if last_error:
                    print(last_error)
                return None
        except Exception as e:
            print(f"分析图像错误: {str(e)}")
            return None
