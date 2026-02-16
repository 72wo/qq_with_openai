"""好友验证 HMAC Token 生成/验证"""

import hmac
import time
import base64
import hashlib
import logging
import re

logger = logging.getLogger(__name__)

# Token 时间窗口默认 10 分钟
_DEFAULT_WINDOW_SEC = 600


class FriendVerificationService:
    """基于 HMAC-SHA256 的好友验证令牌"""

    def __init__(self, secret: str, window_sec: int = _DEFAULT_WINDOW_SEC):
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.window_sec = window_sec

    # ------------------------------------------------------------------
    # Token 格式: {base64url_hmac}.{time_window}
    # ------------------------------------------------------------------
    def generate_token(self, qq_number: str) -> str:
        """为指定 QQ 号生成验证 Token"""
        qq_number = qq_number.strip()
        if not re.match(r"^[1-9]\d{4,11}$", qq_number):
            raise ValueError("QQ 号格式无效 (5-12 位数字，不以 0 开头)")

        time_window = self._current_window()
        sig = self._sign(qq_number, time_window)
        return f"{sig}.{time_window}"

    def verify_token(self, qq_number: str, token: str) -> bool:
        """验证好友请求中的 Token"""
        qq_number = qq_number.strip()
        token = token.strip()

        parts = token.split(".")
        if len(parts) != 2:
            return False

        sig, window_str = parts
        try:
            provided_window = int(window_str)
        except ValueError:
            return False

        # 检查时间窗口是否在有效范围内
        current_window = self._current_window()
        # 允许前一个窗口（防止边界问题）
        if provided_window not in (current_window, current_window - 1):
            logger.info(f"Token 时间窗口已过期: {provided_window} vs {current_window}")
            return False

        expected_sig = self._sign(qq_number, provided_window)
        return hmac.compare_digest(sig, expected_sig)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _current_window(self) -> int:
        return int(time.time()) // self.window_sec

    def _sign(self, qq_number: str, time_window: int) -> str:
        message = f"{qq_number}|{time_window}".encode("utf-8")
        digest = hmac.new(self._secret, message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
