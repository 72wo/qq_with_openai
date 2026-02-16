"""安全规则基类与请求上下文"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequestContext:
    """从请求中提取的安全检查上下文"""
    ip: str = ""
    path: str = ""
    method: str = ""
    user_agent: str = ""
    content_length: int = 0
    status_code: int = 0          # 响应完成后回填
    is_auth_failure: bool = False  # 401
    is_login_failure: bool = False # 登录端点且失败
    is_websocket: bool = False
    timestamp: float = field(default_factory=time.time)


class BaseRule(ABC):
    """安全规则抽象基类"""

    # ---- 子类必须覆盖的元信息 ----
    rule_id: str = ""
    description: str = ""
    default_enabled: bool = True
    default_threshold: int = 5
    default_window_sec: int = 300
    default_ban_duration_sec: int = 3600

    def __init__(self) -> None:
        self.enabled: bool = self.default_enabled
        self.threshold: int = self.default_threshold
        self.window_sec: int = self.default_window_sec
        self.ban_duration_sec: int = self.default_ban_duration_sec

    # ---- 子类实现 ----
    @abstractmethod
    def check(self, ctx: RequestContext, tracker: "IPTracker") -> Optional[str]:
        """返回封禁理由字符串 or None"""
        ...

    # ---- 序列化 ----
    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "enabled": self.enabled,
            "threshold": self.threshold,
            "window_sec": self.window_sec,
            "ban_duration_sec": self.ban_duration_sec,
        }

    def update_from_dict(self, data: dict) -> None:
        if "enabled" in data:
            self.enabled = bool(data["enabled"])
        if "threshold" in data:
            self.threshold = max(1, int(data["threshold"]))
        if "window_sec" in data:
            self.window_sec = max(1, int(data["window_sec"]))
        if "ban_duration_sec" in data:
            self.ban_duration_sec = max(10, int(data["ban_duration_sec"]))


class IPTracker:
    """单个 IP 的滑动窗口计数器集合"""

    def __init__(self) -> None:
        self.buckets: dict[str, list[float]] = {}
        self.endpoints: list[tuple[float, str]] = []  # (ts, path)

    def record(self, bucket: str, ts: float | None = None) -> None:
        ts = ts or time.time()
        self.buckets.setdefault(bucket, []).append(ts)

    def count(self, bucket: str, window_sec: int) -> int:
        now = time.time()
        cutoff = now - window_sec
        events = self.buckets.get(bucket, [])
        # 惰性清理
        events[:] = [t for t in events if t > cutoff]
        return len(events)

    def record_endpoint(self, path: str, ts: float | None = None) -> None:
        ts = ts or time.time()
        self.endpoints.append((ts, path))

    def unique_endpoints(self, window_sec: int) -> int:
        now = time.time()
        cutoff = now - window_sec
        self.endpoints = [(t, p) for t, p in self.endpoints if t > cutoff]
        return len({p for t, p in self.endpoints})

    def cleanup(self, max_age: int = 7200) -> None:
        """清理过期数据"""
        cutoff = time.time() - max_age
        for key in list(self.buckets):
            self.buckets[key] = [t for t in self.buckets[key] if t > cutoff]
            if not self.buckets[key]:
                del self.buckets[key]
        self.endpoints = [(t, p) for t, p in self.endpoints if t > cutoff]
