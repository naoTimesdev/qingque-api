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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp
from blacksheep import Content, Response, json
from blacksheep.server.controllers import Controller, get

from app.settings import Settings
from domain.i18n import QingqueI18n, QingqueLanguage
from domain.mihomo.client import MihomoAPI
from domain.mihomo.models.player import Player
from domain.starrail.caching import StarRailImageCache
from domain.starrail.generator.mihomo import StarRailMihomoCard
from domain.starrail.generator.player import StarRailPlayerCard
from domain.starrail.loader import SRSDataLoaderI18n
from domain.starrail.scoring import RelicScoring
from domain.transcations import TransactionMihomo, TransactionsHelper


@dataclass
class ErrorResponse:
    code: int
    message: str
    data: Any | None = None


class MihomoCharactersGenerator(Controller):
    def __init__(
        self,
        settings: Settings,
        mihomo: MihomoAPI,
        transactions: TransactionsHelper,
        i18n: QingqueI18n,
        srs_cache: StarRailImageCache,
        srs_i18n: SRSDataLoaderI18n,
        relic_scores: RelicScoring,
    ) -> None:
        self.i18n = i18n
        self.srs_cache = srs_cache
        self.srs_i18n = srs_i18n
        self.settings = settings
        self.mihomo = mihomo
        self.transactions = transactions
        self.relic_scores = relic_scores

    @classmethod
    def route(cls) -> str | None:
        return "/api/mihomo/profile"

    @classmethod
    def class_name(cls) -> str:
        return "Generator"

    @get()
    async def create(
        self,
        character: int = 1,
        uid: int | None = None,
        token: str | None = None,
        lang: str = "en-US",
        detailed: bool = False,
    ):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return json(ErrorResponse(400, "Invalid language"), 400)

        if uid is None and token is None:
            return json(ErrorResponse(400, "Missing uid or token"), 400)

        data: Player | None = None
        if token is not None:
            cached = await self.transactions.get(token, type=TransactionMihomo)
            if cached is None:
                return json(ErrorResponse(400, "Invalid token provided"), 400)
            uid = cached.uid
            data = cached.cached

        if uid is not None and data is None:
            try:
                data, _ = await self.mihomo.get_player(uid)
            except aiohttp.ClientResponseError as e:
                error_ = f"Unable to get Mihomo data for {uid}: {e.message} ({e.status})"
                return json(ErrorResponse(400, error_), 400)

        if data is None:
            return json(ErrorResponse(400, "Invalid uid"), 400)

        try:
            character_sel = data.characters[character - 1]
        except IndexError:
            return json(ErrorResponse(400, "Invalid character"), 400)

        mihomo_gen = StarRailMihomoCard(
            character=character_sel,
            player=data.player,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            relic_scorer=self.relic_scores,
            img_cache=self.srs_cache,
        )

        results = await mihomo_gen.create(clear_cache=False, hide_credits=True, detailed=detailed)

        filename = f"{uid}_{character_sel.id}_Card{q_lang.name}.Qingque.png"

        # Cache response for 5 minutes
        # Results is PNG bytes
        return Response(
            200,
            headers=[
                (b"Content-Disposition", f"inline; filename={filename}".encode("utf-8")),
                (b"Cache-Control", b"max-age=300, must-revalidate"),
            ],
            content=Content(
                b"image/png",
                data=results,
            ),
        )


class MihomoProfileGenerator(Controller):
    def __init__(
        self,
        settings: Settings,
        mihomo: MihomoAPI,
        transactions: TransactionsHelper,
        i18n: QingqueI18n,
        srs_cache: StarRailImageCache,
        srs_i18n: SRSDataLoaderI18n,
        relic_scores: RelicScoring,
    ) -> None:
        self.i18n = i18n
        self.srs_cache = srs_cache
        self.srs_i18n = srs_i18n
        self.settings = settings
        self.mihomo = mihomo
        self.transactions = transactions
        self.relic_scores = relic_scores

    @classmethod
    def route(cls) -> str | None:
        return "/api/mihomo/player"

    @classmethod
    def class_name(cls) -> str:
        return "Generator"

    @get()
    async def create(
        self,
        uid: int | None = None,
        token: str | None = None,
        lang: str = "en-US",
    ):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return json(ErrorResponse(400, "Invalid language"), 400)

        if uid is None and token is None:
            return json(ErrorResponse(400, "Missing uid or token"), 400)

        data: Player | None = None
        if token is not None:
            cached = await self.transactions.get(token, type=TransactionMihomo)
            if cached is None:
                return json(ErrorResponse(400, "Invalid token provided"), 400)
            uid = cached.uid
            data = cached.cached

        if uid is not None and data is None:
            try:
                data, _ = await self.mihomo.get_player(uid)
            except aiohttp.ClientResponseError as e:
                error_ = f"Unable to get Mihomo data for {uid}: {e.message} ({e.status})"
                return json(ErrorResponse(400, error_), 400)

        if data is None:
            return json(ErrorResponse(400, "Invalid uid"), 400)

        mihomo_gen = StarRailPlayerCard(
            player=data,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        results = await mihomo_gen.create(clear_cache=False)

        filename = f"PlayerCard{q_lang.name}_{uid}.Qingque.png"

        # Cache response for 10 minutes
        # Results is PNG bytes
        return Response(
            200,
            headers=[
                (b"Content-Disposition", f"inline; filename={filename}".encode("utf-8")),
                (b"Cache-Control", b"public, max-age=600"),
            ],
            content=Content(
                b"image/png",
                data=results,
            ),
        )
