"""模式匹配类安全规则"""

import re
from typing import Optional
from .base import BaseRule, RequestContext, IPTracker

# ---- 预编译正则 ----
_MALICIOUS_UA_PATTERNS = re.compile(
    r"(sqlmap|nikto|nmap|masscan|hydra|medusa|dirbuster|gobuster|"
    r"wfuzz|nessus|openvas|acunetix|burpsuite|havij|pangolin|"
    r"zmeu|morfeus|scanner|exploit|attack)",
    re.IGNORECASE,
)

_SQL_INJECTION_PATTERNS = re.compile(
    r"(\bunion\b.*\bselect\b|\bor\b\s+1\s*=\s*1|\bdrop\b.*\btable\b|"
    r"\binsert\b.*\binto\b|\bdelete\b.*\bfrom\b|\bupdate\b.*\bset\b|"
    r"--|;.*--|/\*.*\*/|\bexec\b|\bexecute\b|\bxp_|0x[0-9a-f]{8}|"
    r"'\s*(or|and)\s+'|char\s*\(|concat\s*\(|benchmark\s*\(|sleep\s*\()",
    re.IGNORECASE,
)

_XSS_PATTERNS = re.compile(
    r"(<script\b|javascript:|on(load|error|click|mouse|focus|blur)\s*=|"
    r"<iframe\b|<object\b|<embed\b|<svg\b.*?on\w+=|eval\s*\(|"
    r"document\.(cookie|domain|write)|window\.(location|open)|"
    r"<img\b[^>]*\bonerror\b)",
    re.IGNORECASE,
)


class MaliciousUARule(BaseRule):
    rule_id = "malicious_ua"
    description = "恶意 User-Agent 检测"
    default_threshold = 1
    default_window_sec = 1
    default_ban_duration_sec = 86400

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if ctx.user_agent and _MALICIOUS_UA_PATTERNS.search(ctx.user_agent):
            return f"恶意 UA: {ctx.user_agent[:80]}"
        return None


class PathScanningRule(BaseRule):
    rule_id = "path_scanning"
    description = "路径扫描检测 (404)"
    default_threshold = 20
    default_window_sec = 300
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if ctx.status_code != 404:
            return None
        tracker.record("path_scan_404", ctx.timestamp)
        cnt = tracker.count("path_scan_404", self.window_sec)
        if cnt >= self.threshold:
            return f"404 次数 {cnt}/{self.window_sec}s"
        return None


class SqlInjectionRule(BaseRule):
    rule_id = "sql_injection"
    description = "SQL 注入模式检测"
    default_threshold = 1
    default_window_sec = 1
    default_ban_duration_sec = 86400

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if _SQL_INJECTION_PATTERNS.search(ctx.path):
            return f"疑似 SQL 注入: {ctx.path[:80]}"
        return None


class XssPatternRule(BaseRule):
    rule_id = "xss_pattern"
    description = "XSS 攻击模式检测"
    default_threshold = 1
    default_window_sec = 1
    default_ban_duration_sec = 86400

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        if _XSS_PATTERNS.search(ctx.path):
            return f"疑似 XSS: {ctx.path[:80]}"
        return None


class MalformedRequestRule(BaseRule):
    rule_id = "malformed_request"
    description = "畸形请求检测"
    default_threshold = 10
    default_window_sec = 300
    default_ban_duration_sec = 3600

    def check(self, ctx: RequestContext, tracker: IPTracker) -> Optional[str]:
        # 检测空 UA、不合法方法等
        is_malformed = False
        if not ctx.user_agent:
            is_malformed = True
        if ctx.method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}:
            is_malformed = True
        if "\x00" in ctx.path:
            is_malformed = True
        if not is_malformed:
            return None
        tracker.record("malformed", ctx.timestamp)
        cnt = tracker.count("malformed", self.window_sec)
        if cnt >= self.threshold:
            return f"畸形请求 {cnt} 次/{self.window_sec}s"
        return None
