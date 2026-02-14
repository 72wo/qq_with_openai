"""图像处理模块"""

import base64
from pathlib import Path
from typing import Optional, List, Dict
from PIL import Image
import io
import httpx


class ImageProcessor:
    """图像处理器"""

    def __init__(self):
        self.max_image_size = 5 * 1024 * 1024  # 5MB

    def is_image_url(self, url: str) -> bool:
        """检查是否是图像 URL"""
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
        return any(url.lower().endswith(ext) for ext in image_extensions)

    def is_base64_image(self, data: str) -> bool:
        """检查是否是 Base64 编码的图像"""
        try:
            if data.startswith('data:image/'):
                return True
            # 尝试解码，看是否是有效的 Base64
            base64.b64decode(data, validate=True)
            return True
        except:
            return False

    def extract_images_from_message(self, message_content: str, images: Optional[List[str]] = None) -> List[str]:
        """从消息中提取图像（URL 或 Base64）"""
        extracted_images = []

        # 从专门的 images 字段提取
        if images:
            for img in images:
                if self.is_image_url(img) or self.is_base64_image(img):
                    extracted_images.append(img)

        # 从消息内容中提取 URL
        import re
        url_pattern = r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp))'
        urls = re.findall(url_pattern, message_content, re.IGNORECASE)
        for url in urls:
            if url not in extracted_images:
                extracted_images.append(url)

        return extracted_images

    def validate_image_size(self, image_data: str) -> bool:
        """验证图像大小"""
        try:
            # 如果是 URL，无法直接验证大小，返回 False 以触发下载和处理
            if image_data.startswith(('http://', 'https://')):
                return False
                
            if image_data.startswith('data:image/'):
                # 移除 data URI 前缀
                image_data = image_data.split(',')[1]

            # 修复 base64 padding
            image_data = self._fix_base64_padding(image_data)
            
            # 检查 Base64 解码后的大小（大约是压缩前的 75%）
            decoded_size = len(base64.b64decode(image_data))
            return decoded_size <= self.max_image_size
        except:
            return False

    def _fix_base64_padding(self, data: str) -> str:
        """修复 base64 padding 问题"""
        # 移除可能的空白字符
        data = data.strip()
        # 补齐 padding
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return data

    async def download_image(self, url: str) -> Optional[str]:
        """下载图像并转换为 data URI"""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 获取内容类型
                content_type = response.headers.get('content-type', 'image/jpeg')
                if ';' in content_type:
                    content_type = content_type.split(';')[0]
                
                # 如果内容类型不是图像，尝试检测
                if not content_type.startswith('image/'):
                    content_type = 'image/jpeg'
                
                # 转换为 base64
                encoded = base64.b64encode(response.content).decode()
                return f"data:{content_type};base64,{encoded}"
        except Exception as e:
            print(f"下载图像失败: {url[:50]}... 错误: {e}")
            return None

    def resize_image(self, image_data: str, max_width: int = 1024, max_height: int = 1024) -> str:
        """调整图像大小（如果需要）"""
        try:
            # 从 Base64 或 data URI 中提取图像数据
            if image_data.startswith('data:image/'):
                image_data = image_data.split(',')[1]

            # 修复 base64 padding
            image_data = self._fix_base64_padding(image_data)
            
            # 解码 Base64
            image_bytes = base64.b64decode(image_data)

            # 打开图像
            image = Image.open(io.BytesIO(image_bytes))

            # 调整大小（保持比例）
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # 转换回 Base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            resized_base64 = base64.b64encode(buffered.getvalue()).decode()

            return f"data:image/jpeg;base64,{resized_base64}"
        except Exception as e:
            print(f"图像调整错误: {str(e)}")
            return image_data

    async def prepare_images_for_vision_api(self, images: List[str]) -> List[str]:
        """准备图像用于 Vision API 调用"""
        prepared = []

        for img in images:
            if not img:
                continue

            if self._is_local_file_path(img):
                img = self._local_file_to_data_uri(img)
                if not img:
                    continue
            elif img.startswith(('http://', 'https://')):
                # 下载远程图像并转换为 data URI
                print(f"下载远程图像: {img[:80]}...")
                downloaded = await self.download_image(img)
                if not downloaded:
                    print(f"跳过无法下载的图像")
                    continue
                img = downloaded

            # 验证大小并压缩
            if not self.validate_image_size(img):
                print(f"图像过大，进行压缩...")
                img = self.resize_image(img)

            # 确保是正确的格式
            if not img.startswith('data:image/'):
                img = f"data:image/jpeg;base64,{img}"
            prepared.append(img)

        return prepared

    def _is_local_file_path(self, image: str) -> bool:
        if image.startswith(("http://", "https://", "data:image/")):
            return False
        path = Path(image)
        return path.exists() and path.is_file()

    def _local_file_to_data_uri(self, file_path: str) -> Optional[str]:
        try:
            path = Path(file_path)
            raw = path.read_bytes()
            ext = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }
            mime = mime_map.get(ext, "image/jpeg")
            encoded = base64.b64encode(raw).decode()
            return f"data:{mime};base64,{encoded}"
        except Exception:
            return None
