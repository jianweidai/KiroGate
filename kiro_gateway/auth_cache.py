# -*- coding: utf-8 -*-

# KiroGate
# Based on kiro-openai-gateway by Jwadow (https://github.com/Jwadow/kiro-openai-gateway)
# Original Copyright (C) 2025 Jwadow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
AuthManager Cache for Multi-Tenant Support.

Manages multiple KiroAuthManager instances for different refresh tokens.
Supports LRU cache with configurable max size.
"""

import asyncio
from collections import OrderedDict
from typing import Optional

from loguru import logger

from kiro_gateway.auth import KiroAuthManager
from kiro_gateway.config import settings


class AuthManagerCache:
    """
    LRU Cache for KiroAuthManager instances.

    Supports multiple users with different refresh tokens.
    Thread-safe using asyncio.Lock.

    Attributes:
        max_size: Maximum number of cached AuthManager instances
        cache: OrderedDict mapping refresh_token -> AuthManager
        lock: Async lock for thread safety
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize AuthManager cache.

        Args:
            max_size: Maximum number of cached instances (default: 100)
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, KiroAuthManager] = OrderedDict()
        self.lock = asyncio.Lock()
        logger.info(f"AuthManager cache initialized with max_size={max_size}")

    async def get_or_create(
        self,
        refresh_token: str,
        region: Optional[str] = None,
        profile_arn: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> KiroAuthManager:
        """
        Get or create AuthManager for given refresh token.

        Uses LRU cache: moves accessed items to end, evicts oldest when full.

        Args:
            refresh_token: Kiro refresh token
            region: AWS region (defaults to settings.region)
            profile_arn: AWS profile ARN (defaults to settings.profile_arn)
            client_id: OAuth client ID (for IDC mode)
            client_secret: OAuth client secret (for IDC mode)

        Returns:
            KiroAuthManager instance for the refresh token
        """
        actual_region = region or settings.region
        # 使用 refresh_token + region 作为缓存 key，确保不同 region 的 token 不会混淆
        cache_key = f"{refresh_token}:{actual_region}"
        
        async with self.lock:
            # Check if already cached
            if cache_key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(cache_key)
                logger.debug(f"AuthManager cache hit for token: {self._mask_token(refresh_token)}, region: {actual_region}")
                return self.cache[cache_key]

            # Create new AuthManager with IDC support
            logger.info(f"Creating new AuthManager for token: {self._mask_token(refresh_token)}, region: {actual_region}")
            auth_manager = KiroAuthManager(
                refresh_token=refresh_token,
                region=actual_region,
                profile_arn=profile_arn or settings.profile_arn,
                client_id=client_id,
                client_secret=client_secret,
            )
            logger.info(f"AuthManager created with api_host: {auth_manager.api_host}")

            # Add to cache
            self.cache[cache_key] = auth_manager

            # Evict oldest if cache is full
            if len(self.cache) > self.max_size:
                oldest_key, oldest_manager = self.cache.popitem(last=False)
                logger.info(
                    f"AuthManager cache full, evicted oldest: {oldest_key[:20]}..."
                )

            logger.debug(f"AuthManager cache size: {len(self.cache)}/{self.max_size}")
            return auth_manager

    async def clear(self) -> None:
        """Clear all cached AuthManager instances."""
        async with self.lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"AuthManager cache cleared, removed {count} instances")

    async def remove(self, refresh_token: str, region: Optional[str] = None) -> bool:
        """
        Remove specific AuthManager from cache.

        Args:
            refresh_token: Refresh token to remove
            region: AWS region (if None, removes all regions for this token)

        Returns:
            True if removed, False if not found
        """
        async with self.lock:
            if region:
                # Remove specific region
                cache_key = f"{refresh_token}:{region}"
                if cache_key in self.cache:
                    del self.cache[cache_key]
                    logger.info(f"Removed AuthManager from cache: {self._mask_token(refresh_token)}, region: {region}")
                    return True
                return False
            else:
                # Remove all regions for this token
                keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{refresh_token}:")]
                for key in keys_to_remove:
                    del self.cache[key]
                if keys_to_remove:
                    logger.info(f"Removed {len(keys_to_remove)} AuthManager(s) from cache for token: {self._mask_token(refresh_token)}")
                    return True
                return False

    def _mask_token(self, token: str) -> str:
        """
        Mask token for logging (show only first and last 4 chars).

        Args:
            token: Token to mask

        Returns:
            Masked token string
        """
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


# Global cache instance
auth_cache = AuthManagerCache(max_size=100)
