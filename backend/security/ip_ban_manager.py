"""IP 封禁核心逻辑 + JSON 持久化"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

from .rules import RULE_REGISTRY, DEFAULT_ENABLED, RequestContext
from .rules.base import BaseRule, IPTracker

logger = logging.getLogger(__name__)

# 默认白名单 IP（本地回环）
_DEFAULT_WHITELIST = {"127.0.0.1", "::1"}


class IPBanManager:
    """IP 封禁管理器"""

    def __init__(self, data_path: str) -> None:
        self._path = Path(data_path)
        self._bans: dict[str, dict] = {}       # ip → {reason, expires, rule_id, manual}
        self._trackers: dict[str, IPTracker] = {}
        self._rules: dict[str, BaseRule] = {}
        self._whitelist: set[str] = set(_DEFAULT_WHITELIST)
        self._init_rules()
        self._load()

    # ------------------------------------------------------------------
    # 规则管理
    # ------------------------------------------------------------------
    def _init_rules(self) -> None:
        for rule_id, cls in RULE_REGISTRY.items():
            rule = cls()
            rule.enabled = rule_id in DEFAULT_ENABLED
            self._rules[rule_id] = rule

    def get_rules(self) -> list[dict]:
        return [r.to_dict() for r in self._rules.values()]

    def update_rule(self, rule_id: str, data: dict) -> bool:
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        rule.update_from_dict(data)
        self.save()
        return True

    # ------------------------------------------------------------------
    # 封禁管理
    # ------------------------------------------------------------------
    def is_banned(self, ip: str) -> Optional[dict]:
        """返回封禁信息或 None"""
        if ip in self._whitelist:
            return None
        ban = self._bans.get(ip)
        if not ban:
            return None
        if ban["expires"] and time.time() > ban["expires"]:
            del self._bans[ip]
            return None
        return ban

    def ban_ip(self, ip: str, reason: str, duration_sec: int,
               rule_id: str = "manual", manual: bool = False) -> None:
        expires = time.time() + duration_sec if duration_sec > 0 else 0
        self._bans[ip] = {
            "reason": reason,
            "expires": expires,
            "rule_id": rule_id,
            "manual": manual,
            "banned_at": time.time(),
        }
        logger.warning(f"IP 已封禁: {ip} — {reason} (规则: {rule_id}, {duration_sec}s)")
        self.save()

    def unban_ip(self, ip: str) -> bool:
        if ip in self._bans:
            del self._bans[ip]
            self.save()
            return True
        return False

    def get_bans(self) -> list[dict]:
        now = time.time()
        result = []
        expired = []
        for ip, ban in self._bans.items():
            if ban["expires"] and now > ban["expires"]:
                expired.append(ip)
                continue
            result.append({
                "ip": ip,
                "reason": ban["reason"],
                "rule_id": ban["rule_id"],
                "manual": ban.get("manual", False),
                "banned_at": ban.get("banned_at", 0),
                "expires": ban["expires"],
                "remaining_sec": max(0, int(ban["expires"] - now)) if ban["expires"] else -1,
            })
        for ip in expired:
            del self._bans[ip]
        return result

    # ------------------------------------------------------------------
    # 请求检查（由中间件调用）
    # ------------------------------------------------------------------
    def check_request(self, ctx: RequestContext) -> Optional[str]:
        """检查请求，如果需要封禁则返回理由"""
        if ctx.ip in self._whitelist:
            return None
        if self.is_banned(ctx.ip):
            return None  # 已封禁，由中间件直接返回 403

        tracker = self._trackers.setdefault(ctx.ip, IPTracker())
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            reason = rule.check(ctx, tracker)
            if reason:
                self.ban_ip(ctx.ip, reason, rule.ban_duration_sec, rule.rule_id)
                return reason
        return None

    def record_response(self, ctx: RequestContext) -> None:
        """响应后的规则检查（需要 status_code）"""
        if ctx.ip in self._whitelist:
            return
        tracker = self._trackers.setdefault(ctx.ip, IPTracker())
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            # 仅对需要 status_code 的规则做后置检查
            if rule.rule_id in ("path_scanning", "auth_failure"):
                reason = rule.check(ctx, tracker)
                if reason:
                    self.ban_ip(ctx.ip, reason, rule.ban_duration_sec, rule.rule_id)

    # ------------------------------------------------------------------
    # 白名单
    # ------------------------------------------------------------------
    @property
    def whitelist(self) -> set[str]:
        return self._whitelist

    def add_whitelist(self, ip: str) -> None:
        self._whitelist.add(ip)
        self.save()

    def remove_whitelist(self, ip: str) -> None:
        self._whitelist.discard(ip)
        self.save()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def save(self) -> None:
        data = {
            "rules": {r_id: r.to_dict() for r_id, r in self._rules.items()},
            "bans": self._bans,
            "whitelist": list(self._whitelist - _DEFAULT_WHITELIST),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        # 恢复规则配置
        saved_rules = data.get("rules", {})
        for rule_id, cfg in saved_rules.items():
            if rule_id in self._rules:
                self._rules[rule_id].update_from_dict(cfg)

        # 恢复封禁列表（清理过期）
        now = time.time()
        for ip, ban in data.get("bans", {}).items():
            if ban.get("expires") and now > ban["expires"]:
                continue
            self._bans[ip] = ban

        # 恢复自定义白名单
        for ip in data.get("whitelist", []):
            self._whitelist.add(ip)

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------
    def cleanup_trackers(self) -> None:
        """定期清理过期的 tracker 数据"""
        for tracker in self._trackers.values():
            tracker.cleanup()
        # 移除空 tracker
        empty = [ip for ip, t in self._trackers.items()
                 if not t.buckets and not t.endpoints]
        for ip in empty:
            del self._trackers[ip]
