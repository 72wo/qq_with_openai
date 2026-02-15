import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
import json


class OpenAIService:
    """OpenAI API 集成服务"""

    def __init__(self, baseurl: str, apikey: str, model: str, max_tokens: int = 500, timeout: int = 60):
        self.baseurl = baseurl.rstrip('/') if baseurl else "https://api.openai.com/v1"
        self.apikey = apikey
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = aiohttp.ClientTimeout(total=timeout)

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

    async def generate_reply(self, messages: List[Dict[str, str]], system_prompt: str = None, max_tokens: int = None) -> Optional[str]:
        """生成AI回复"""
        try:
            request_messages = []

            if system_prompt:
                request_messages.append({"role": "system", "content": system_prompt})

            request_messages.extend(messages)

            # 使用传入的 max_tokens，如果没有则使用默认值
            tokens = max_tokens if max_tokens is not None else self.max_tokens

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.apikey}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": request_messages,
                    "temperature": 0.7,
                    "max_tokens": tokens
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

            vision_timeout = aiohttp.ClientTimeout(total=20)
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.apikey}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 50,
                    "temperature": 0.3
                }

                async with session.post(
                    f"{self.baseurl}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=vision_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()[:40]
                    return None
        except Exception as e:
            print(f"分析图像错误: {str(e)}")
            return None
