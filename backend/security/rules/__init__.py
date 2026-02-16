"""安全规则注册表"""

from .base import BaseRule, RequestContext
from .rate_rules import (
    LoginFailureRule,
    ApiRateMinuteRule,
    ApiRateHourRule,
    TokenPageRateRule,
    BruteForceRule,
)
from .connection_rules import (
    ConcurrentConnectionsRule,
    RequestBodySizeRule,
    WebSocketAbuseRule,
)
from .pattern_rules import (
    MaliciousUARule,
    PathScanningRule,
    SqlInjectionRule,
    XssPatternRule,
    MalformedRequestRule,
)
from .behavioral_rules import (
    AuthFailureRule,
    RapidEndpointSwitchRule,
    SlowHttpRule,
)

# 所有可用规则 (ID → 类)
RULE_REGISTRY: dict[str, type[BaseRule]] = {
    "login_failure":          LoginFailureRule,
    "api_rate_minute":        ApiRateMinuteRule,
    "api_rate_hour":          ApiRateHourRule,
    "concurrent_connections": ConcurrentConnectionsRule,
    "auth_failure":           AuthFailureRule,
    "malicious_ua":           MaliciousUARule,
    "path_scanning":          PathScanningRule,
    "token_page_rate":        TokenPageRateRule,
    "request_body_size":      RequestBodySizeRule,
    "sql_injection":          SqlInjectionRule,
    "xss_pattern":            XssPatternRule,
    "rapid_endpoint_switch":  RapidEndpointSwitchRule,
    "malformed_request":      MalformedRequestRule,
    "brute_force":            BruteForceRule,
    "websocket_abuse":        WebSocketAbuseRule,
    "slow_http":              SlowHttpRule,
}

# 默认启用的规则
DEFAULT_ENABLED = {
    "login_failure", "api_rate_minute", "api_rate_hour",
    "concurrent_connections", "auth_failure", "malicious_ua",
    "path_scanning", "token_page_rate", "request_body_size",
    "sql_injection", "xss_pattern", "malformed_request",
    "brute_force", "websocket_abuse",
}

__all__ = [
    'BaseRule', 'RequestContext', 'RULE_REGISTRY', 'DEFAULT_ENABLED',
]
