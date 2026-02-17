"""认证管理器 — 密码哈希 + JWT 签发/验证"""

import json
import hmac
import secrets
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import bcrypt
import jwt

logger = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS_DEFAULT = 24


class AuthManager:
    """管理员认证: bcrypt 密码 + JWT 会话"""

    def __init__(self, auth_path: str):
        self._path = Path(auth_path)
        self._data: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # 初始化（首次启动时生成密码并打印）
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if self._data.get("initialized"):
            logger.info("认证信息已存在，跳过初始化")
            return

        plain_password = secrets.token_urlsafe(12)
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(plain_password.encode(), salt).decode()
        jwt_secret = secrets.token_hex(32)
        friend_secret = secrets.token_hex(32)

        self._data = {
            "password_hash": password_hash,
            "jwt_secret": jwt_secret,
            "friend_verification_secret": friend_secret,
            "initialized": True,
        }
        self._save()

        print("\n" + "=" * 50)
        print("  管理员初始密码: " + plain_password)
        print("  请登录后立即修改密码!")
        print("=" * 50 + "\n")
        logger.info("已生成初始管理员密码（见上方控制台输出）")

    # ------------------------------------------------------------------
    # 密码操作
    # ------------------------------------------------------------------
    def verify_password(self, plain: str) -> bool:
        stored = self._data.get("password_hash", "")
        if not stored:
            return False
        return bcrypt.checkpw(plain.encode(), stored.encode())

    def change_password(self, old_plain: str, new_plain: str) -> bool:
        if not self.verify_password(old_plain):
            return False
        salt = bcrypt.gensalt(rounds=12)
        self._data["password_hash"] = bcrypt.hashpw(new_plain.encode(), salt).decode()
        self._save()
        logger.info("管理员密码已修改")
        return True

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------
    @property
    def session_expiry_hours(self) -> int:
        """获取会话有效时长（小时），0 表示永不过期
        """
        return self._data.get("session_expiry_hours", _JWT_EXPIRY_HOURS_DEFAULT)

    def set_session_expiry_hours(self, hours: int) -> None:
        """设置会话有效时长（小时），0 表示永不过期"""
        self._data["session_expiry_hours"] = hours
        self._save()
        logger.info(f"会话有效时长已修改为 {hours} 小时" if hours else "会话有效时长已设置为永不过期")

    def create_token(self) -> str:
        now = datetime.now(timezone.utc)
        expiry_hours = self.session_expiry_hours
        payload = {
            "sub": "admin",
            "iat": now,
        }
        if expiry_hours > 0:
            payload["exp"] = now + timedelta(hours=expiry_hours)
        return jwt.encode(payload, self._jwt_secret, algorithm=_JWT_ALGORITHM)

    def validate_token(self, token: str) -> Optional[dict]:
        try:
            options = {}
            if self.session_expiry_hours == 0:
                options["verify_exp"] = False
            return jwt.decode(token, self._jwt_secret, algorithms=[_JWT_ALGORITHM], options=options)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    # ------------------------------------------------------------------
    # 好友验证密钥
    # ------------------------------------------------------------------
    @property
    def friend_verification_secret(self) -> str:
        return self._data.get("friend_verification_secret", "")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    @property
    def _jwt_secret(self) -> str:
        return self._data.get("jwt_secret", "")

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
