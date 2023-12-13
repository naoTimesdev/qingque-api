"""
MIT License

Copyright (c) 2023-present naoTimesdev

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Transactions helper

from __future__ import annotations

import secrets
from typing import TypeVar

from msgspec import Struct, field

from domain.mihomo.models import Player as MihomoPlayer
from domain.redisdb import RedisDatabase

__all__ = (
    "TransactionHoyolab",
    "TransactionsHelper",
    "TransactionCacheKind",
)


class TransactionHoyolab(Struct):
    uid: int
    """:class:`int`: The user game UID."""
    ltuid: int
    """:class:`int`: The user HoyoLab UID."""
    ltoken: str
    """:class:`str`: The user HoyoLab token."""
    lcookie: str | None = field(default=None)
    """:class:`str | None`: The user HoyoLab cookie."""
    lmid: str | None = field(default=None)
    """:class:`str | None`: The user HoyoLab MID."""


class TransactionMihomo(Struct):
    uid: int
    cached: MihomoPlayer


class TransactionCacheKind:
    MIHOMO = "mihomo"
    MIHOMO_PLAYER = "mihomo:player"
    HY_CHRONICLES = "hoyolab:chronicles"
    HY_MOC = "hoyolab:moc"
    HY_SIMUNIVERSE = "hoyolab:simulated_universe"

    @classmethod
    def is_valid(cls, kind: str) -> bool:
        return kind in (
            cls.MIHOMO,
            cls.MIHOMO_PLAYER,
            cls.HY_CHRONICLES,
            cls.HY_MOC,
            cls.HY_SIMUNIVERSE,
        )

    @classmethod
    def make(cls, kind: str, extra_meta: str | None = None) -> str:
        if not cls.is_valid(kind):
            raise ValueError(f"Invalid cache kind: {kind}")

        return f"{kind}:{extra_meta}" if extra_meta else kind


TransT = TypeVar("TransT", bound=Struct)


class TransactionsHelper:
    KEY = "qingque:transactions"

    def __init__(self, *, redis: RedisDatabase) -> None:
        self._redis = redis

    @property
    def redis(self) -> RedisDatabase:
        return self._redis

    async def get(self, token: str, *, type: type[TransT]) -> TransT | None:
        """Get a transaction from the database."""
        data = await self._redis.get(f"{self.KEY}:{token}", type=type)
        return data

    async def create(self, transaction: Struct, *, ttl: int) -> str:
        """Create a transaction in the database."""

        token = secrets.token_hex(32)
        await self._redis.setex(f"{self.KEY}:{token}", transaction, ttl)
        return token

    async def get_gen_cache(self, token: str, cache_type: str) -> bytes | None:
        """Get a cache from the database."""
        data = await self._redis.get(f"{self.KEY}:{token}:{cache_type}")
        return data

    async def set_gen_cache(self, token: str, cache_type: str, data: bytes, *, ttl: int) -> None:
        """Set a cache in the database."""
        await self._redis.setex(f"{self.KEY}:{token}:{cache_type}", data, expires=ttl)
