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
_JWT_EXPIRY_HOURS = 24


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
    def create_token(self) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin",
            "iat": now,
            "exp": now + timedelta(hours=_JWT_EXPIRY_HOURS),
        }
        return jwt.encode(payload, self._jwt_secret, algorithm=_JWT_ALGORITHM)

    def validate_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, self._jwt_secret, algorithms=[_JWT_ALGORITHM])
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
