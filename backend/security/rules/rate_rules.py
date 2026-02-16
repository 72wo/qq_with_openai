"""频率类安全规则"""

from typing import Optional
from .base import BaseRule, RequestContext, IPTracker


class LoginFailureRule(BaseRule):
    rule_id = "login_failure"
    description = "登录失败频率限制"
    default_threshold = 5
    default_window_sec = 300
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if not ctx.is_login_failure:
            return None
        tracker.record("login_failure", ctx.timestamp)
        cnt = tracker.count("login_failure", self.window_sec)
        if cnt >= self.threshold:
            return f"登录失败 {cnt} 次/{self.window_sec}s"
        return None


class ApiRateMinuteRule(BaseRule):
    rule_id = "api_rate_minute"
    description = "API 每分钟请求频率限制"
    default_threshold = 120
    default_window_sec = 60
    default_ban_duration_sec = 600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        tracker.record("api_rate_minute", ctx.timestamp)
        cnt = tracker.count("api_rate_minute", self.window_sec)
        if cnt >= self.threshold:
            return f"每分钟请求 {cnt} 次"
        return None


class ApiRateHourRule(BaseRule):
    rule_id = "api_rate_hour"
    description = "API 每小时请求频率限制"
    default_threshold = 3000
    default_window_sec = 3600
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        tracker.record("api_rate_hour", ctx.timestamp)
        cnt = tracker.count("api_rate_hour", self.window_sec)
        if cnt >= self.threshold:
            return f"每小时请求 {cnt} 次"
        return None


class TokenPageRateRule(BaseRule):
    rule_id = "token_page_rate"
    description = "Token 页面请求频率限制"
    default_threshold = 10
    default_window_sec = 300
    default_ban_duration_sec = 1800

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if not (ctx.path.startswith("/token") or ctx.path.startswith("/api/friend/")):
            return None
        tracker.record("token_page_rate", ctx.timestamp)
        cnt = tracker.count("token_page_rate", self.window_sec)
        if cnt >= self.threshold:
            return f"Token 页面请求 {cnt} 次/{self.window_sec}s"
        return None


class BruteForceRule(BaseRule):
    rule_id = "brute_force"
    description = "暴力请求检测"
    default_threshold = 30
    default_window_sec = 10
    default_ban_duration_sec = 1800

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        tracker.record("brute_force", ctx.timestamp)
        cnt = tracker.count("brute_force", self.window_sec)
        if cnt >= self.threshold:
            return f"10 秒内请求 {cnt} 次"
        return None
