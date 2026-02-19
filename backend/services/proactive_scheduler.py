"""主动消息调度引擎 — 让 AI 像真人一样主动聊天

设计原则:
1. 所有主动消息由 AI 通过策略提示词生成，保持人格一致性
2. 多层频率限制防止骚扰：全局/单目标/策略维度
3. 时间随机抖动模拟真人不规律行为
4. 作用域白名单/黑名单精准控制覆盖范围
"""

import asyncio
import random
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── 16 种策略定义（每种自带 AI 提示词模板）────────────────────

STRATEGY_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "morning_greeting": {
        "label": "早安问候",
        "description": "在早晨时段发送自然的问候，分享对新一天的期待",
        "prompt_template": "现在是早晨，你想主动跟{target_label}打招呼。用你自己的风格发一条自然的早安消息，可以提到天气、心情或今天的小期待。不要太正式，像朋友间随意的早安。一两句话即可。",
        "time_range": [6, 10],
        "default_weight": 1.0,
        "target_types": ["friend", "group"],
    },
    "night_greeting": {
        "label": "晚安告别",
        "description": "在夜晚发送温馨的晚安消息",
        "prompt_template": "现在是晚上了，你想跟{target_label}说晚安。用你自己的风格发一条温馨的晚安消息。可以简单回顾一下'今天的感受'或者表达对明天的期待。一两句话，自然不做作。",
        "time_range": [21, 24],
        "default_weight": 1.0,
        "target_types": ["friend", "group"],
    },
    "random_thought": {
        "label": "随机碎碎念",
        "description": "突然冒出的生活感悟或日常吐槽",
        "prompt_template": "你突然想到了一个有趣的想法或生活感悟，想分享给{target_label}。就像刷社交媒体时突然想发条动态的那种冲动。内容随意自然，可以是吐槽、感慨、奇怪的念头。一两句话。",
        "time_range": [9, 23],
        "default_weight": 0.5,
        "target_types": ["friend", "group"],
    },
    "ask_question": {
        "label": "好奇提问",
        "description": "出于好奇心向对方提一个有趣或有深度的问题",
        "prompt_template": "你对{target_label}很好奇，想问一个有趣的问题。可以是关于生活、喜好、有趣的假设性问题，或者'你觉得...'开头的问题。要真的能引发对话，不要太无聊。一句话提问。",
        "time_range": [10, 22],
        "default_weight": 0.6,
        "target_types": ["friend"],
    },
    "share_topic": {
        "label": "话题分享",
        "description": "主动抛出一个好玩的话题引发讨论",
        "prompt_template": "你发现了一个有趣的话题想跟{target_label}聊。可以是科技、生活、美食、旅行、影视等任何方面。像是'诶你知道吗...'或'我最近发现...'的语气。两三句话，要能引发讨论。",
        "time_range": [10, 22],
        "default_weight": 0.5,
        "target_types": ["friend", "group"],
    },
    "care_check": {
        "label": "关心问候",
        "description": "隔一段时间没聊天时主动关心对方近况",
        "prompt_template": "你好久没跟{target_label}聊天了，想主动关心一下。不要太正式，就像朋友间自然地问一下近况。比如'最近怎么样啊'、'在忙什么呢'之类。一两句话，语气轻松。",
        "time_range": [10, 21],
        "default_weight": 0.7,
        "target_types": ["friend"],
    },
    "humor_share": {
        "label": "幽默互动",
        "description": "分享一个有趣的想法、冷笑话或段子",
        "prompt_template": "你想到了一个好笑的事情或者段子，想分享给{target_label}逗他们开心。可以是冷笑话、谐音梗、有趣的现象，或者网络热门笑点。要真的好笑或至少有意思。两三句话。",
        "time_range": [10, 23],
        "default_weight": 0.4,
        "target_types": ["friend", "group"],
    },
    "encouragement": {
        "label": "鼓励打气",
        "description": "适时给好友加油鼓励",
        "prompt_template": "你想给{target_label}打打气、加加油。不用太鸡汤，就像朋友间自然的鼓励。可以说'加油'的变体，或者分享一个积极的小观点。一两句话，真诚不做作。",
        "time_range": [9, 21],
        "default_weight": 0.3,
        "target_types": ["friend"],
    },
    "memory_recall": {
        "label": "旧事重提",
        "description": "回忆之前聊过的话题，延续之前的缘分",
        "prompt_template": "你突然想起了之前的某次聊天内容，想跟{target_label}重新聊聊那个话题。就像'诶我突然想起我们之前聊的那个...'的感觉。编造一个合理的之前可能聊过的话题。一两句话。",
        "time_range": [10, 22],
        "default_weight": 0.3,
        "target_types": ["friend"],
    },
    "festival_greeting": {
        "label": "节日祝福",
        "description": "在节假日或特殊日子发送应景的祝福",
        "prompt_template": "今天可能是某个节日或有纪念意义的日子（当前日期: {date}），你想给{target_label}发送一条应景的祝福。如果今天确实是节日就送节日祝福，如果不是也可以编一个有趣的'今日宜...'。用你自己的风格，不要太正式。一两句话。",
        "time_range": [8, 22],
        "default_weight": 0.8,
        "target_types": ["friend", "group"],
    },
    "weather_talk": {
        "label": "天气闲聊",
        "description": "用天气或季节作为话题切入点",
        "prompt_template": "你想用天气作为话题跟{target_label}闲聊。根据当前月份({month}月)编造一个合理的天气相关话题，比如太热了太冷了下雨了等等。就像真人会说的'今天也太热了吧'之类。一两句话。",
        "time_range": [8, 21],
        "default_weight": 0.4,
        "target_types": ["friend", "group"],
    },
    "emotion_share": {
        "label": "心情分享",
        "description": "分享当下的心情或情绪状态",
        "prompt_template": "你想跟{target_label}分享你现在的心情。随机选一种心情（开心、有点无聊、感慨、兴奋、平静等），用自然的语气表达。像发朋友圈或跟朋友吐露心声。一两句话。",
        "time_range": [9, 23],
        "default_weight": 0.4,
        "target_types": ["friend"],
    },
    "daily_summary": {
        "label": "每日小结",
        "description": "在傍晚分享一天的感想",
        "prompt_template": "一天快结束了，你想跟{target_label}分享今天的感想。编造一些合理的今日经历或感悟，像是朋友间的日常分享。比如'今天做了XX感觉还不错'。两三句话。",
        "time_range": [17, 22],
        "default_weight": 0.3,
        "target_types": ["friend"],
    },
    "interest_discuss": {
        "label": "兴趣交流",
        "description": "发起关于共同兴趣（游戏/动漫/音乐等）的讨论",
        "prompt_template": "你想跟{target_label}聊一些有趣的兴趣话题，比如最近的游戏、动漫、音乐、电影、书籍等。像是'你玩过XX吗'、'最近在追什么番'的感觉。一两句话，自然地发起。",
        "time_range": [10, 23],
        "default_weight": 0.5,
        "target_types": ["friend", "group"],
    },
    "continue_conversation": {
        "label": "接续话题",
        "description": "对之前中断的对话主动接续",
        "prompt_template": "你跟{target_label}之前的聊天中断了，你想主动接续。可以说'对了刚才说到哪了'、'说起之前那个话题...'或者用一个新的角度继续之前可能讨论的内容。一两句话。",
        "time_range": [9, 23],
        "default_weight": 0.4,
        "target_types": ["friend"],
    },
    "sudden_inspiration": {
        "label": "灵感一闪",
        "description": "突然想到的奇妙想法或脑洞大开的念头",
        "prompt_template": "你突然灵感一闪，想到了一个很有意思的想法/脑洞/发现，忍不住想分享给{target_label}。就像'我突然想到一个事'、'你有没有想过...'的感觉。要有点意思或者出人意料。一两句话。",
        "time_range": [10, 23],
        "default_weight": 0.4,
        "target_types": ["friend", "group"],
    },
}

# 策略 ID 列表（保持稳定顺序）
STRATEGY_IDS = list(STRATEGY_DEFINITIONS.keys())


def get_default_proactive_config() -> dict:
    """生成默认的主动消息配置"""
    strategies = {}
    for sid, sdef in STRATEGY_DEFINITIONS.items():
        strategies[sid] = {
            "enabled": False,
            "weight": sdef["default_weight"],
        }
    return {
        "enabled": False,
        "scope_mode": "disabled",
        "friend_whitelist": [],
        "friend_blacklist": [],
        "group_whitelist": [],
        "group_blacklist": [],
        "global_daily_max": 30,
        "per_friend_daily_max": 3,
        "per_group_daily_max": 2,
        "min_interval_minutes": 30,
        "active_hours_start": 8,
        "active_hours_end": 23,
        "strategies": strategies,
    }


class ProactiveScheduler:
    """主动消息调度引擎

    核心调度算法:
    1. 每 check_interval 秒检查一次是否该发消息
    2. 使用随机抖动确定下次行动时间（拟人不规律性）
    3. 筛选可用目标 → 加权随机选目标
    4. 筛选当前可用策略 → 加权随机选策略
    5. 用 AI 生成消息内容 → 发送 → 更新计数器
    """

    def __init__(self, config, napcat_client, openai_service_factory, message_handler_factory=None):
        self.config = config
        self.napcat_client = napcat_client
        self._openai_factory = openai_service_factory        # callable() -> OpenAIService
        self._message_handler_factory = message_handler_factory  # callable() -> MessageHandler | None

        # 运行状态
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 频率限制计数器（内存，重启清零）
        self._global_daily_count = 0
        self._daily_reset_date: Optional[str] = None
        self._target_daily_count: Dict[str, int] = defaultdict(int)  # target_key -> count
        self._target_last_time: Dict[str, float] = {}  # target_key -> timestamp
        self._next_action_time: float = 0.0

        # 统计
        self._total_sent = 0
        self._last_sent_time: Optional[float] = None
        self._last_strategy: Optional[str] = None
        self._last_target: Optional[str] = None

    # ── 生命周期 ──────────────────────────────────────────

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("主动消息调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("主动消息调度器已停止")

    def restart(self):
        """重启调度器（配置变更后调用）"""
        self.stop()
        pc = self.config.get("proactive", {})
        if pc.get("enabled", False):
            self.start()

    def get_status(self) -> dict:
        """获取调度器运行状态（供 API 查询）"""
        pc = self.config.get("proactive", {})
        return {
            "running": self._running,
            "enabled": pc.get("enabled", False),
            "total_sent_today": self._global_daily_count,
            "total_sent_all": self._total_sent,
            "daily_limit": pc.get("global_daily_max", 30),
            "last_sent_time": self._last_sent_time,
            "last_strategy": STRATEGY_DEFINITIONS.get(self._last_strategy, {}).get("label") if self._last_strategy else None,
            "last_target": self._last_target,
            "next_action_in": max(0, int(self._next_action_time - time.time())) if self._next_action_time > time.time() else 0,
        }

    # ── 主调度循环 ────────────────────────────────────────

    async def _scheduler_loop(self):
        """主调度循环"""
        logger.info("主动消息调度循环启动")
        # 首次延迟随机 1-5 分钟再开始，避免启动就发
        self._next_action_time = time.time() + random.uniform(60, 300)

        while self._running:
            try:
                await asyncio.sleep(30)  # 每 30 秒检查一次

                if not self._should_act():
                    continue

                # 执行一次主动消息
                await self._perform_action()

                # 计算下次行动时间（带随机抖动，±30%）
                pc = self.config.get("proactive", {})
                base_interval = max(5, pc.get("min_interval_minutes", 30)) * 60
                jitter = random.uniform(0.7, 1.5)
                self._next_action_time = time.time() + base_interval * jitter
                logger.debug(f"下次主动消息在 {base_interval * jitter / 60:.1f} 分钟后")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主动消息调度循环异常: {e}")
                await asyncio.sleep(60)  # 出错后休息 1 分钟

        logger.info("主动消息调度循环结束")

    def _should_act(self) -> bool:
        """判断当前是否应该执行主动消息"""
        pc = self.config.get("proactive", {})

        # 0. 功能未启用
        if not pc.get("enabled", False):
            return False

        # 1. NapCat 未连接
        if not self.napcat_client or not self.napcat_client.is_connected:
            return False

        # 2. 未到行动时间
        if time.time() < self._next_action_time:
            return False

        # 3. 活跃时间段检查
        now = datetime.now()
        hour = now.hour
        start_h = pc.get("active_hours_start", 8)
        end_h = pc.get("active_hours_end", 23)
        if start_h <= end_h:
            if not (start_h <= hour < end_h):
                return False
        else:  # 跨午夜，如 22:00-06:00
            if end_h <= hour < start_h:
                return False

        # 4. 日计数重置
        today = now.strftime("%Y-%m-%d")
        if self._daily_reset_date != today:
            self._daily_reset_date = today
            self._global_daily_count = 0
            self._target_daily_count.clear()

        # 5. 全局日限额
        if self._global_daily_count >= pc.get("global_daily_max", 30):
            return False

        return True

    async def _perform_action(self):
        """执行一次主动消息发送"""
        pc = self.config.get("proactive", {})

        # 1. 获取可用目标
        targets = await self._get_eligible_targets(pc)
        if not targets:
            logger.debug("主动消息: 无可用目标")
            return

        # 2. 获取当前可用策略
        strategies = self._get_eligible_strategies(pc)
        if not strategies:
            logger.debug("主动消息: 无可用策略")
            return

        # 3. 加权随机选目标
        target = self._weighted_pick(targets, key=lambda t: t.get("_score", 1.0))

        # 4. 根据目标类型过滤策略
        target_type = target.get("type", "friend")
        valid_strategies = [
            s for s in strategies
            if target_type in STRATEGY_DEFINITIONS.get(s["id"], {}).get("target_types", [])
        ]
        if not valid_strategies:
            valid_strategies = strategies  # fallback

        # 5. 加权随机选策略
        strategy = self._weighted_pick(valid_strategies, key=lambda s: s.get("weight", 0.5))

        # 6. 生成消息
        message = await self._generate_message(strategy, target, pc)
        if not message:
            logger.warning("主动消息: AI 生成消息失败")
            return

        # 7. 发送
        success = await self._send_message(target, message)
        if not success:
            return

        # 8. 更新计数器
        target_key = target.get("key", "")
        self._global_daily_count += 1
        self._target_daily_count[target_key] += 1
        self._target_last_time[target_key] = time.time()
        self._total_sent += 1
        self._last_sent_time = time.time()
        self._last_strategy = strategy.get("id", "")
        self._last_target = target.get("label", target_key)

        # 9. 写入对话历史（让后续收到用户回复时能衔接上下文）
        self._write_to_history(target, message)

        # 10. 记录日志
        from ..app import append_recent_message
        append_recent_message({
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "event_type": "proactive",
            "message_type": target_type,
            "user_id": target.get("user_id", ""),
            "group_id": target.get("group_id", ""),
            "message_id": "",
            "content": f"[主动·{STRATEGY_DEFINITIONS.get(strategy['id'], {}).get('label', '?')}] {message}",
        })

        logger.info(
            f"主动消息已发送: 策略={strategy['id']}, "
            f"目标={target.get('label', target_key)}, "
            f"今日已发={self._global_daily_count}"
        )

    # ── 手动触发（纯测试，绕过一切调度约束） ─────────────

    async def manual_trigger(self):
        """手动触发一次主动消息（测试用）。

        特性：
        - 不要求调度器处于运行状态
        - 不受冷却时间、日限额、活跃时段等限制
        - 不会更新任何计数器 / 冷却记录
        - 不会影响正常调度节奏
        """
        pc = self.config.get("proactive", {})

        # 1. 获取所有目标（跳过冷却 & 日限额）
        targets = await self._get_eligible_targets(pc, force=True)
        if not targets:
            logger.warning("手动触发: 无可用目标（白名单为空或 NapCat 未连接）")
            return False

        # 2. 获取策略（跳过时间段限制）
        strategies = self._get_eligible_strategies(pc, force=True)
        if not strategies:
            logger.warning("手动触发: 无已启用的策略")
            return False

        # 3. 加权随机选目标
        target = self._weighted_pick(targets, key=lambda t: t.get("_score", 1.0))

        # 4. 按目标类型过滤策略
        target_type = target.get("type", "friend")
        valid_strategies = [
            s for s in strategies
            if target_type in STRATEGY_DEFINITIONS.get(s["id"], {}).get("target_types", [])
        ]
        if not valid_strategies:
            valid_strategies = strategies

        # 5. 加权随机选策略
        strategy = self._weighted_pick(valid_strategies, key=lambda s: s.get("weight", 0.5))

        # 6. 生成消息
        message = await self._generate_message(strategy, target, pc)
        if not message:
            logger.warning("手动触发: AI 生成消息失败")
            return False

        # 7. 发送
        success = await self._send_message(target, message)
        if not success:
            return False

        # 8. 仅更新展示用统计，不更新冷却 / 限额计数器
        self._total_sent += 1
        self._last_sent_time = time.time()
        self._last_strategy = strategy.get("id", "")
        self._last_target = target.get("label", target.get("key", ""))

        # 9. 写入对话历史
        self._write_to_history(target, message)

        # 10. 记录日志
        from ..app import append_recent_message
        append_recent_message({
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "event_type": "proactive_manual",
            "message_type": target_type,
            "user_id": target.get("user_id", ""),
            "group_id": target.get("group_id", ""),
            "message_id": "",
            "content": f"[手动测试·{STRATEGY_DEFINITIONS.get(strategy['id'], {}).get('label', '?')}] {message}",
        })

        logger.info(
            f"手动触发主动消息已发送: 策略={strategy['id']}, "
            f"目标={target.get('label', target.get('key', ''))}"
        )
        return True

    # ── 写入对话历史 ─────────────────────────────────────

    def _write_to_history(self, target: dict, message: str):
        """将主动消息以 assistant 身份写入 message_handler 的对话历史。

        这样当用户回复时，AI 能看到自己之前主动说了什么，实现真正的上下文衔接。
        chat_key 格式与 napcat_client 保持一致：
          - 好友私聊: private:{user_id}
          - 群聊:     group:{group_id}
        """
        if not self._message_handler_factory:
            return
        mh = self._message_handler_factory()
        if not mh:
            return

        if target.get("type") == "group":
            chat_key = f"group:{target['group_id']}"
        else:
            chat_key = f"private:{target['user_id']}"

        try:
            mh._append_to_history(chat_key, "assistant", message)
            logger.debug(f"主动消息已写入对话历史: {chat_key}")
        except Exception as e:
            logger.warning(f"写入对话历史失败: {e}")

    # ── 目标筛选 ────────────────────────────────────────

    async def _get_eligible_targets(self, pc: dict, *, force: bool = False) -> List[dict]:
        """获取可用的目标列表（好友 + 群）"""
        scope_mode = pc.get("scope_mode", "disabled")
        if scope_mode == "disabled":
            return []

        targets = []
        min_interval = max(5, pc.get("min_interval_minutes", 30)) * 60
        per_friend_max = pc.get("per_friend_daily_max", 3)
        per_group_max = pc.get("per_group_daily_max", 2)
        now = time.time()

        # 获取好友列表
        try:
            friends = await self.napcat_client.get_friend_list()
        except Exception:
            friends = []

        # 获取 bot 自身 ID 以排除
        bot_id = ""
        try:
            login_info = await self.napcat_client.get_login_info()
            if login_info:
                bot_id = login_info.get("user_id", "")
        except Exception:
            pass

        friend_wl = set(pc.get("friend_whitelist", []))
        friend_bl = set(pc.get("friend_blacklist", []))
        group_wl = set(pc.get("group_whitelist", []))
        group_bl = set(pc.get("group_blacklist", []))

        for f in friends:
            uid = str(f.get("user_id", ""))
            if not uid or uid == bot_id:
                continue

            # 作用域过滤
            if scope_mode == "whitelist" and uid not in friend_wl:
                continue
            if scope_mode == "blacklist" and uid in friend_bl:
                continue

            key = f"friend:{uid}"
            last = self._target_last_time.get(key, 0)
            if not force:
                # 冷却检查
                if now - last < min_interval:
                    continue
                # 日限额检查
                if self._target_daily_count.get(key, 0) >= per_friend_max:
                    continue

            label = f.get("remark") or f.get("nickname") or uid
            # 越久没聊的得分越高（鼓励关心久未联系的人）
            idle_hours = (now - last) / 3600 if last > 0 else 24
            score = min(3.0, 0.5 + idle_hours / 12)

            targets.append({
                "type": "friend",
                "user_id": uid,
                "group_id": "",
                "key": key,
                "label": label,
                "_score": score,
            })

        # 群聊目标仅从白名单/黑名单获取
        if scope_mode == "whitelist":
            for gid in group_wl:
                key = f"group:{gid}"
                last = self._target_last_time.get(key, 0)
                if not force:
                    if now - last < min_interval:
                        continue
                    if self._target_daily_count.get(key, 0) >= per_group_max:
                        continue
                idle_hours = (now - last) / 3600 if last > 0 else 24
                score = min(2.0, 0.3 + idle_hours / 24)
                targets.append({
                    "type": "group",
                    "user_id": "",
                    "group_id": gid,
                    "key": key,
                    "label": f"群{gid}",
                    "_score": score,
                })

        return targets

    def _get_eligible_strategies(self, pc: dict, *, force: bool = False) -> List[dict]:
        """获取当前时间可用的策略列表（支持分钟精度，优先使用策略覆盖）"""
        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute
        strategies_cfg = pc.get("strategies", {})
        result = []

        for sid, sdef in STRATEGY_DEFINITIONS.items():
            scfg = strategies_cfg.get(sid, {})
            if not scfg.get("enabled", False):
                continue

            # 时间段检查：优先使用策略配置的 time_range（已存为分钟整数），否则使用定义中的时间（小时级）
            def to_min(x):
                if isinstance(x, int):
                    # 小于等于 24 的视为小时
                    return x * 60 if x <= 24 else x
                if isinstance(x, str):
                    m = re.match(r"^(\d{1,2}):(\d{2})$", x.strip())
                    if not m:
                        raise ValueError(f"无法解析时间格式: {x!r}")
                    hh = int(m.group(1)); mm = int(m.group(2))
                    return hh * 60 + mm
                return int(x)

            tr = scfg.get("time_range", sdef.get("time_range", [0, 24]))
            t_start_min = to_min(tr[0])
            t_end_min = to_min(tr[1])

            if not force:
                if t_start_min <= t_end_min:
                    if not (t_start_min <= now_minutes < t_end_min):
                        continue
                else:
                    # 跨日区间
                    if t_end_min <= now_minutes < t_start_min:
                        continue

            weight = scfg.get("weight", sdef.get("default_weight", 0.5))
            result.append({
                "id": sid,
                "weight": weight,
                "prompt_template": sdef["prompt_template"],
            })

        return result

    # ── 消息生成 ────────────────────────────────────────

    async def _generate_message(self, strategy: dict, target: dict, pc: dict) -> Optional[str]:
        """通过 AI 生成主动消息"""
        openai_service = self._openai_factory()
        if not openai_service:
            return None

        # 构建提示词
        now = datetime.now()
        target_label = target.get("label", "对方")
        if target.get("type") == "group":
            target_label = f"群里的大家"

        prompt = strategy["prompt_template"].format(
            target_label=target_label,
            date=now.strftime("%Y年%m月%d日"),
            time=now.strftime("%H:%M"),
            month=now.month,
        )

        # 使用 bot 的人格 prompt 作为 system
        base_prompt = self.config.get("bot.prompt", "你是一个友好的 AI 助手")
        beijing_time_str = now.strftime("%Y年%m月%d日 %H:%M")
        
        # 根据目标类型构建不同的提示
        target_type = target.get("type", "friend")
        if target_type == "group":
            context_hint = (
                f"你现在要在一个群聊中主动发言。"
                f"群里有多个人，你的消息会被所有人看到。"
                f"注意：你的称呼和表达方式要适应多人环境，"
                f"可以是对所有人的问候或分享，而不是针对单个人。"
            )
        else:
            context_hint = f"你现在要主动跟这个人发消息。"
        
        system_prompt = (
            f"{base_prompt}\n\n"
            f"[主动消息指令] {context_hint}"
            f"当前北京时间: {beijing_time_str}。"
            f"要求：保持你一贯的说话风格和人设，语气自然随意，"
            f"像真人发的一样，不要有AI感。"
            f"直接输出消息内容即可，不要加引号、不要说'我会发送'之类。"
        )

        # 添加回复长度建议（来自"单条消息建议长度"配置）
        suggested_len = int(self.config.get("features.context_message_max_chars", 0) or 0)
        if suggested_len > 0:
            system_prompt += f"\n请将回复控制在约{suggested_len}个字符左右。"

        try:
            messages = [{"role": "user", "content": prompt}]
            reply = await openai_service.generate_reply(messages, system_prompt)
            if reply:
                # 清理可能的引号包裹
                reply = reply.strip().strip('"').strip("'").strip('"').strip('"')
            return reply
        except Exception as e:
            logger.error(f"主动消息 AI 生成失败: {e}")
            return None

    async def _send_message(self, target: dict, message: str) -> bool:
        """发送消息到目标"""
        try:
            if target.get("type") == "group":
                return await self.napcat_client.send_message(
                    group_id=target.get("group_id"),
                    content=message,
                )
            else:
                return await self.napcat_client.send_message(
                    user_id=target.get("user_id"),
                    content=message,
                )
        except Exception as e:
            logger.error(f"主动消息发送失败: {e}")
            return False

    # ── 工具方法 ────────────────────────────────────────

    @staticmethod
    def _weighted_pick(items: list, key=None) -> Any:
        """加权随机选择"""
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        weights = [key(item) if key else 1.0 for item in items]
        total = sum(weights)
        if total <= 0:
            return random.choice(items)
        return random.choices(items, weights=weights, k=1)[0]

    @staticmethod
    def get_strategy_definitions() -> List[dict]:
        """返回策略定义列表（供前端展示）"""
        result = []
        for sid, sdef in STRATEGY_DEFINITIONS.items():
            result.append({
                "id": sid,
                "label": sdef["label"],
                "description": sdef["description"],
                "time_range": sdef.get("time_range", [0, 24]),
                "default_weight": sdef.get("default_weight", 0.5),
                "target_types": sdef.get("target_types", []),
            })
        return result
