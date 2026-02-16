"""连接类安全规则"""

from typing import Optional
from .base import BaseRule, RequestContext, IPTracker


class ConcurrentConnectionsRule(BaseRule):
    rule_id = "concurrent_connections"
    description = "单 IP 并发连接限制"
    default_threshold = 20
    default_window_sec = 60
    default_ban_duration_sec = 1800

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        # 用 1 秒窗口的请求量近似并发数
        tracker.record("concurrent", ctx.timestamp)
        cnt = tracker.count("concurrent", 1)
        if cnt >= self.threshold:
            return f"并发连接约 {cnt}"
        return None


class RequestBodySizeRule(BaseRule):
    rule_id = "request_body_size"
    description = "请求体过大检测"
    default_threshold = 1048576  # 1 MB
    default_window_sec = 1
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if ctx.content_length > self.threshold:
            return f"请求体 {ctx.content_length} 字节 > {self.threshold}"
        return None


class WebSocketAbuseRule(BaseRule):
    rule_id = "websocket_abuse"
    description = "WebSocket 连接滥用"
    default_threshold = 10
    default_window_sec = 60
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if not ctx.is_websocket:
            return None
        tracker.record("ws_connect", ctx.timestamp)
        cnt = tracker.count("ws_connect", self.window_sec)
        if cnt >= self.threshold:
            return f"WebSocket 连接 {cnt} 次/{self.window_sec}s"
        return None
