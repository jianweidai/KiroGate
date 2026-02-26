# -*- coding: utf-8 -*-

"""
KiroGate 智能 Token 分配器。

实现基于成功率、冷却时间和负载均衡的 Token 智能分配算法。
"""

import asyncio
import random
import time
from typing import Any, Optional, Tuple, List

from loguru import logger

from kiro_gateway.database import user_db, DonatedToken
from kiro_gateway.auth import KiroAuthManager
from kiro_gateway.config import settings, SLOW_MODELS, PRO_PLUS_MODELS


def requires_pro_plus(model: str) -> bool:
    """Check if the model requires a Pro+ token (opus_enabled=True)."""
    if not model:
        return False
    # 先检查精确匹配（含内部 ID）
    if model in PRO_PLUS_MODELS:
        return True
    model_lower = model.lower()
    # 包含 opus 关键字
    if "opus" in model_lower:
        return True
    # sonnet-4-6 / sonnet-4.6
    if "sonnet" in model_lower and ("4-6" in model_lower or "4.6" in model_lower):
        return True
    return False


# 向后兼容别名
def is_opus_model(model: str) -> bool:
    return requires_pro_plus(model)


class NoTokenAvailable(Exception):
    """No active token available for allocation."""
    pass


def _account_matches_model(account: dict, model: str) -> bool:
    """判断 Custom API 账号是否绑定了指定模型（逗号分隔，精确匹配，忽略首尾空格）。"""
    raw = (account.get("model") or "").strip()
    if not raw:
        return False
    return model in {m.strip() for m in raw.split(",")}


class SmartTokenAllocator:
    """智能 Token 分配器。"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._token_managers: dict[int, KiroAuthManager] = {}
        # 追踪每个 Token 最近的请求次数（用于短期负载均衡）
        self._recent_usage: dict[int, int] = {}
        self._last_reset = time.time()

    def _reset_recent_usage_if_needed(self) -> None:
        """每分钟重置一次短期使用计数，确保负载均衡在短时间窗口内生效。"""
        now = time.time()
        if now - self._last_reset > 60:  # 每分钟重置
            self._recent_usage.clear()
            self._last_reset = now

    def calculate_score(self, token: DonatedToken) -> float:
        """
        计算 Token 评分 (0-100)。

        评分基于：
        - 成功率 (权重 40%)：保证可靠性
        - 冷却时间 (权重 30%)：最近使用的得低分，实现轮换
        - 负载均衡 (权重 30%)：短期内使用次数少的优先
        """
        now = int(time.time() * 1000)
        self._reset_recent_usage_if_needed()

        # 1. 成功率分 (权重 40%)
        total = token.success_count + token.fail_count
        if total == 0:
            success_rate = 1.0  # 新 Token 给予高分
        else:
            success_rate = token.success_count / total

        # 如果成功率低于阈值，大幅降分
        if success_rate < settings.token_min_success_rate and total > 10:
            base_score = success_rate * 20  # 严重惩罚
        else:
            base_score = success_rate * 40

        # 2. 冷却时间分 (权重 30%)：最近使用的得低分，长时间未使用的得高分
        if token.last_used:
            seconds_since_use = (now - token.last_used) / 1000
        else:
            seconds_since_use = 3600  # 从未使用，视为 1 小时前

        # 30 秒内使用过的得低分，超过 5 分钟的得满分
        if seconds_since_use < 30:
            cooldown_score = 5  # 刚用过，低分
        elif seconds_since_use < 60:
            cooldown_score = 15
        elif seconds_since_use < 300:
            cooldown_score = 25
        else:
            cooldown_score = 30  # 满分

        # 3. 短期负载均衡分 (权重 30%)：最近 1 分钟内使用次数少的优先
        recent_count = self._recent_usage.get(token.id, 0)
        # 每次使用扣 10 分，最多扣到 0
        balance_score = max(0, 30 - recent_count * 10)

        total_score = base_score + cooldown_score + balance_score
        
        logger.debug(
            f"Token {token.id} 评分: 总分={total_score:.1f} "
            f"(成功率={base_score:.1f}, 冷却={cooldown_score:.1f}, 均衡={balance_score:.1f})"
        )
        
        return total_score

    def _weighted_random_choice(self, tokens: List[DonatedToken]) -> DonatedToken:
        """
        基于评分的加权随机选择。
        
        评分高的 Token 有更高的概率被选中，但不是绝对的。
        这样可以在保证高质量 Token 优先的同时，实现负载均衡。
        """
        if len(tokens) == 1:
            return tokens[0]
        
        # 计算每个 Token 的评分
        scores = [(t, self.calculate_score(t)) for t in tokens]
        
        # 确保所有分数为正（加一个小常数避免 0 权重）
        min_score = min(s for _, s in scores)
        if min_score <= 0:
            scores = [(t, s - min_score + 1) for t, s in scores]
        
        # 加权随机选择
        total_weight = sum(s for _, s in scores)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for token, score in scores:
            cumulative += score
            if r <= cumulative:
                return token
        
        # 兜底返回最后一个
        return scores[-1][0]

    def _record_recent_usage(self, token_id: int) -> None:
        """记录短期使用次数。"""
        self._reset_recent_usage_if_needed()
        self._recent_usage[token_id] = self._recent_usage.get(token_id, 0) + 1

    async def get_best_token(self, user_id: Optional[int] = None, model: Optional[str] = None) -> Tuple[str, Any, Optional[KiroAuthManager]]:
        """
        获取最优 Token 或 Custom API 账号。

        对于有用户的请求，将用户的私有 Kiro Token 和 Custom API 账号合并后随机选择。
        否则使用公共 Token 池（仅 Kiro Token）。

        Args:
            user_id: 用户 ID（可选）
            model: 请求的模型名称（可选）

        Returns:
            (account_type, account_data, manager) tuple
            - account_type: 'kiro' 或 'custom_api'
            - account_data: DonatedToken（kiro）或 dict（custom_api）
            - manager: KiroAuthManager（kiro）或 None（custom_api）

        Raises:
            NoTokenAvailable: 无可用 Token 或账号
        """
        from kiro_gateway.metrics import metrics
        self_use_enabled = metrics.is_self_use_enabled()
        
        # 检查是否请求 Pro+ 专属模型
        requesting_pro_plus = requires_pro_plus(model) if model else False

        if user_id:
            # 用户请求: 获取用户的私有 Kiro Token
            user_tokens = user_db.get_user_tokens(user_id, limit=None)
            
            logger.info(f"用户 {user_id} 的所有 Token: {[(t.id, t.status, t.visibility, t.opus_enabled) for t in user_tokens]}")
            
            active_kiro_tokens = [
                t for t in user_tokens
                if t.status == "active" and (not self_use_enabled or t.visibility == "private")
            ]
            
            logger.info(f"用户 {user_id} 的活跃 Kiro Token (self_use={self_use_enabled}): {[(t.id, t.opus_enabled) for t in active_kiro_tokens]}")

            # 获取用户的 active Custom API 账号
            custom_api_accounts = user_db.get_active_custom_api_accounts_by_user(user_id)
            logger.info(f"用户 {user_id} 的活跃 Custom API 账号: {len(custom_api_accounts)} 个")

            # 如果请求 Pro+ 专属模型，合并 Pro+ Kiro Token 和绑定该模型的 Custom API 账号
            if requesting_pro_plus:
                pro_tokens = [t for t in active_kiro_tokens if t.opus_enabled]
                pro_custom = [a for a in custom_api_accounts if _account_matches_model(a, model)]

                if pro_tokens or pro_custom:
                    logger.info(
                        f"Pro+ 轮询: 用户 {user_id} 有 {len(pro_tokens)} 个 Pro+ Token, "
                        f"{len(pro_custom)} 个绑定了 {model} 的 Custom API 账号"
                    )
                    if pro_tokens and pro_custom:
                        if random.random() < len(pro_tokens) / (len(pro_tokens) + len(pro_custom)):
                            best = self._weighted_random_choice(pro_tokens)
                            self._record_recent_usage(best.id)
                            logger.info(f"Pro+ 轮询: 选择了 Kiro Token {best.id}")
                            manager = await self._get_manager(best)
                            return 'kiro', best, manager
                        else:
                            account = random.choice(pro_custom)
                            logger.info(f"Pro+ 轮询: 选择了 Custom API 账号 {account['id']}")
                            return 'custom_api', account, None
                    elif pro_tokens:
                        best = self._weighted_random_choice(pro_tokens)
                        self._record_recent_usage(best.id)
                        logger.info(f"Pro+ 轮询: 选择了 Kiro Token {best.id}")
                        manager = await self._get_manager(best)
                        return 'kiro', best, manager
                    else:
                        account = random.choice(pro_custom)
                        logger.info(f"Pro+ 轮询: 选择了 Custom API 账号 {account['id']}")
                        return 'custom_api', account, None
                else:
                    logger.warning(
                        f"用户 {user_id} 没有 Pro+ Token 也没有绑定 {model} 的 Custom API 账号，"
                        f"回退到全量池"
                    )
                    # fall through to full pool below

            # 合并 Kiro Token 和 Custom API 账号，随机选择
            all_candidates = (
                [('kiro', t) for t in active_kiro_tokens] +
                [('custom_api', a) for a in custom_api_accounts]
            )

            if all_candidates:
                account_type, account_data = random.choice(all_candidates)
                if account_type == 'kiro':
                    self._record_recent_usage(account_data.id)
                    logger.info(f"Token 分配: 用户 {user_id} 选择了 Kiro Token {account_data.id} (共 {len(all_candidates)} 个候选)")
                    manager = await self._get_manager(account_data)
                    return 'kiro', account_data, manager
                else:
                    logger.info(f"Token 分配: 用户 {user_id} 选择了 Custom API 账号 {account_data['id']} (共 {len(all_candidates)} 个候选)")
                    return 'custom_api', account_data, None

            # 用户没有任何可用账号，不回退到公共池
            raise NoTokenAvailable(f"用户 {user_id} 没有可用的 Token 或 Custom API 账号")

        if self_use_enabled:
            raise NoTokenAvailable("Self-use mode: public token pool is disabled")

        # 使用公共 Token 池（仅 Kiro Token，不含 Custom API）
        public_tokens = user_db.get_public_tokens()
        if not public_tokens:
            raise NoTokenAvailable("No public tokens available")

        # 过滤掉低成功率的 Token
        good_tokens = [
            t for t in public_tokens
            if t.success_rate >= settings.token_min_success_rate or
               (t.success_count + t.fail_count) < 10  # 给新Token机会
        ]

        if not good_tokens:
            good_tokens = public_tokens

        # 如果请求 Pro+ 专属模型，优先选择 Pro+ Token
        if requesting_pro_plus:
            pro_tokens = [t for t in good_tokens if t.opus_enabled]
            if pro_tokens:
                best = self._weighted_random_choice(pro_tokens)
                self._record_recent_usage(best.id)
                logger.info(f"Token 分配 (Pro+): 从 {len(pro_tokens)} 个 Pro+ Token 中选择了 Token {best.id}")
                manager = await self._get_manager(best)
                return 'kiro', best, manager
            else:
                logger.warning(f"公共池没有 Pro+ Token，将使用普通 Token")

        # 使用加权随机选择，实现负载均衡
        best = self._weighted_random_choice(good_tokens)
        self._record_recent_usage(best.id)
        
        logger.info(f"Token 分配: 从 {len(good_tokens)} 个可用 Token 中选择了 Token {best.id}")
        
        manager = await self._get_manager(best)
        return 'kiro', best, manager

    async def _get_manager(self, token: DonatedToken) -> KiroAuthManager:
        """获取或创建 Token 对应的 AuthManager（线程安全）。"""
        async with self._lock:
            if token.id in self._token_managers:
                cached_manager = self._token_managers[token.id]
                logger.debug(f"Token {token.id} 使用缓存的 AuthManager, api_host: {cached_manager.api_host}")
                return cached_manager

            # 获取完整凭证信息（包括 IDC 的 client_id 和 client_secret，以及 region）
            credentials = user_db.get_token_credentials(token.id)
            if not credentials or not credentials.get("refresh_token"):
                raise NoTokenAvailable(f"Failed to get credentials for token {token.id}")

            # 使用 Token 的 region，如果不存在则使用默认值 'us-east-1'
            token_region = credentials.get("region", "us-east-1")
            logger.info(f"Token {token.id} 使用 region: {token_region}")

            # 创建 AuthManager，传递完整凭证以支持 IDC 认证模式
            manager = KiroAuthManager(
                refresh_token=credentials["refresh_token"],
                region=token_region,
                profile_arn=settings.profile_arn,
                client_id=credentials.get("client_id"),
                client_secret=credentials.get("client_secret"),
            )
            logger.info(f"Token {token.id} AuthManager api_host: {manager.api_host}")

            self._token_managers[token.id] = manager
            return manager

    def record_usage(self, token_id: int, success: bool) -> None:
        """记录 Token 使用结果。"""
        user_db.record_token_usage(token_id, success)

    def clear_manager(self, token_id: int) -> None:
        """清除缓存的 AuthManager。"""
        if token_id in self._token_managers:
            del self._token_managers[token_id]


# Global allocator instance
token_allocator = SmartTokenAllocator()
