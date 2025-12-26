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
        profile_arn: Optional[str] = None
    ) -> KiroAuthManager:
        """
        Get or create AuthManager for given refresh token.

        Uses LRU cache: moves accessed items to end, evicts oldest when full.

        Args:
            refresh_token: Kiro refresh token
            region: AWS region (defaults to settings.region)
            profile_arn: AWS profile ARN (defaults to settings.profile_arn)

        Returns:
            KiroAuthManager instance for the refresh token
        """
        async with self.lock:
            # Check if already cached
            if refresh_token in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(refresh_token)
                logger.debug(f"AuthManager cache hit for token: {self._mask_token(refresh_token)}")
                return self.cache[refresh_token]

            # Create new AuthManager
            logger.info(f"Creating new AuthManager for token: {self._mask_token(refresh_token)}")
            auth_manager = KiroAuthManager(
                refresh_token=refresh_token,
                region=region or settings.region,
                profile_arn=profile_arn or settings.profile_arn
            )

            # Add to cache
            self.cache[refresh_token] = auth_manager

            # Evict oldest if cache is full
            if len(self.cache) > self.max_size:
                oldest_token, oldest_manager = self.cache.popitem(last=False)
                logger.info(
                    f"AuthManager cache full, evicted oldest token: "
                    f"{self._mask_token(oldest_token)}"
                )

            logger.debug(f"AuthManager cache size: {len(self.cache)}/{self.max_size}")
            return auth_manager

    async def clear(self) -> None:
        """Clear all cached AuthManager instances."""
        async with self.lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"AuthManager cache cleared, removed {count} instances")

    async def remove(self, refresh_token: str) -> bool:
        """
        Remove specific AuthManager from cache.

        Args:
            refresh_token: Refresh token to remove

        Returns:
            True if removed, False if not found
        """
        async with self.lock:
            if refresh_token in self.cache:
                del self.cache[refresh_token]
                logger.info(f"Removed AuthManager from cache: {self._mask_token(refresh_token)}")
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
