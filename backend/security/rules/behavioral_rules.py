"""行为类安全规则"""

from typing import Optional
from .base import BaseRule, RequestContext, IPTracker


class AuthFailureRule(BaseRule):
    rule_id = "auth_failure"
    description = "认证失败次数 (401) 限制"
    default_threshold = 10
    default_window_sec = 300
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if not ctx.is_auth_failure:
            return None
        tracker.record("auth_failure", ctx.timestamp)
        cnt = tracker.count("auth_failure", self.window_sec)
        if cnt >= self.threshold:
            return f"认证失败 {cnt} 次/{self.window_sec}s"
        return None


class RapidEndpointSwitchRule(BaseRule):
    rule_id = "rapid_endpoint_switch"
    description = "快速切换端点检测"
    default_enabled = False
    default_threshold = 30
    default_window_sec = 10
    default_ban_duration_sec = 1800

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        tracker.record_endpoint(ctx.path, ctx.timestamp)
        unique = tracker.unique_endpoints(self.window_sec)
        if unique >= self.threshold:
            return f"{self.window_sec}s 内访问 {unique} 个不同端点"
        return None


class SlowHttpRule(BaseRule):
    rule_id = "slow_http"
    description = "慢速 HTTP 攻击检测"
    default_enabled = False
    default_threshold = 5
    default_window_sec = 30
    default_ban_duration_sec = 7200

    # 判定为"可疑慢速请求"的 Content-Length 下限（字节）
    _MIN_BODY_SIZE = 1024

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        # 低开销启发式：在短窗口内同一 IP 反复发送声明大 body 的 POST/PUT
        # 中间件的 BaseHTTPMiddleware 会等待完整 body，正常客户端不会高频触发
        # 而 Slow POST 攻击者会在窗口内打开大量这样的连接
        if ctx.method not in ("POST", "PUT", "PATCH"):
            return None
        if ctx.content_length < self._MIN_BODY_SIZE:
            return None

        tracker.record("slow_http", ctx.timestamp)
        cnt = tracker.count("slow_http", self.window_sec)
        if cnt >= self.threshold:
            return f"疑似慢速 HTTP 攻击: {self.window_sec}s 内 {cnt} 次大请求体"
        return None
