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

import aiohttp
from blacksheep import Content, Response
from blacksheep.server.controllers import Controller, get
from blacksheep.server.openapi.common import ContentInfo, ResponseExample, ResponseInfo, ResponseStatusType

from app.docs import docs
from app.responses import ErrorCode, ErrorResponse, better_json
from app.settings import Settings
from domain.i18n import QingqueI18n, QingqueLanguage
from domain.mihomo.client import MihomoAPI
from domain.mihomo.models.player import Player
from domain.starrail.caching import StarRailImageCache
from domain.starrail.generator.mihomo import StarRailMihomoCard
from domain.starrail.generator.player import StarRailPlayerCard
from domain.starrail.loader import SRSDataLoaderI18n
from domain.starrail.scoring import RelicScoring
from domain.transcations import TransactionCacheKind, TransactionMihomo, TransactionsHelper
from qutils.tooling import get_logger

_mihomo_resp_info: dict[ResponseStatusType, str | ResponseInfo] = {
    400: ResponseInfo(
        "Bad Request",
        content=[
            ContentInfo(
                ErrorResponse,
                examples=[
                    ResponseExample(
                        ErrorResponse(ErrorCode.MISSING_UID_TOKEN, "Missing uid or token"),
                    )
                ],
            )
        ],
    ),
    403: ResponseInfo(
        "Invalid Token",
        content=[
            ContentInfo(
                ErrorResponse,
                examples=[
                    ResponseExample(
                        ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"),
                    )
                ],
            )
        ],
    ),
    404: ResponseInfo(
        "UID not found",
        content=[
            ContentInfo(
                ErrorResponse,
                examples=[
                    ResponseExample(
                        ErrorResponse(ErrorCode.MIHOMO_UID_NOT_FOUND, "Invalid UID provided"),
                    )
                ],
            )
        ],
    ),
    503: ResponseInfo(
        "Error from Mihomo",
        content=[
            ContentInfo(
                ErrorResponse,
                examples=[
                    ResponseExample(
                        ErrorResponse(
                            ErrorCode.MIHOMO_ERROR,
                            "Unable to get Mihomo data for 1234567890: 503 Service Unavailable (503)",
                        ),
                    )
                ],
            )
        ],
    ),
    200: ResponseInfo(
        "Success",
        content=[ContentInfo(bytes, content_type="image/png")],
    ),
}


class Mihomo(Controller):
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

        self.logger = get_logger("qingque.api.controllers.mihomo")

    @classmethod
    def route(cls) -> str | None:
        return "/api/mihomo"

    def _make_cache_key_chara(self, character_idx: int, lang: QingqueLanguage, detailed: bool):
        mode = "_detailed" if detailed else ""
        return f"INDEX_{character_idx}_{lang.name}{mode}"

    def _make_response(self, filename: str, data: bytes, ttl: int = 300):
        return Response(
            200,
            headers=[
                (b"Content-Disposition", f"inline; filename={filename}".encode("utf-8")),
                (b"Cache-Control", f"max-age={ttl}, must-revalidate".encode("utf-8")),
            ],
            content=Content(
                b"image/png",
                data=data,
            ),
        )

    @get("/")
    @docs(
        summary="Get Mihomo data",
        description="Get Mihomo data from Qingque's cache, if not created yet, use the transactions API",
        tags=["Mihomo"],
        responses={
            403: ResponseInfo(
                "Invalid Token",
                content=[
                    ContentInfo(
                        ErrorResponse,
                        examples=[
                            ResponseExample(
                                ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"),
                            )
                        ],
                    )
                ],
            ),
            200: ResponseInfo(
                "Success",
                content=[
                    ContentInfo(
                        Player,
                        examples=[
                            ResponseExample(
                                Player.mock(),
                            )
                        ],
                    )
                ],
            ),
        },
    )
    async def get_info(self, token: str):
        cached = await self.transactions.get(token, type=TransactionMihomo)
        if cached is None:
            return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)
        data = cached.cached

        return better_json(data)

    @get("/profile.png")
    @docs(
        summary="Create a Mihomo character profile card",
        description="Generate a Mihomo character profile card either from provided token or provided UID.",
        tags=["Mihomo"],
        responses=_mihomo_resp_info,
    )
    async def create_profile_card(
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
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        if uid is None and token is None:
            return better_json(ErrorResponse(ErrorCode.MISSING_UID_TOKEN, "Missing uid or token"), 400)

        cache_meta = self._make_cache_key_chara(character, q_lang, detailed)
        cache_key = TransactionCacheKind.make(
            TransactionCacheKind.MIHOMO,
            extra_meta=cache_meta,
        )

        data: Player | None = None
        if token is not None:
            self.logger.info(f"Checking cache for: {token} (with key: {cache_key})")
            cached = await self.transactions.get(token, type=TransactionMihomo)
            img_cache = await self.transactions.get_gen_cache(token, cache_type=cache_key)
            if cached is None and img_cache is not None:
                self.logger.info(f"Found cache for: {token} (with key: {cache_key})")
                return self._make_response(f"{token}_IDX{character}.QingqueBot.png", img_cache)
            if cached is not None and img_cache is not None:
                self.logger.info(f"Found cache for: {token} (with key: {cache_key})")
                return self._make_response(f"{cached.uid}_IDX{character}.QingqueBot.png", img_cache)
            if cached is None:
                return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)
            uid = cached.uid
            data = cached.cached

        self.logger.info(f"Generating player card for {uid}...")
        if token is not None:
            self.logger.info(f"Using token {token}")

        if uid is not None and data is None:
            try:
                data, _ = await self.mihomo.get_player(uid)
            except aiohttp.ClientResponseError as e:
                status_code = 503 if e.status != 404 else 404
                error_code = ErrorCode.MIHOMO_ERROR if e.status != 404 else ErrorCode.MIHOMO_UID_NOT_FOUND
                error_ = f"Unable to get Mihomo data for {uid}: {e.message} ({e.status})"
                return better_json(ErrorResponse(error_code, error_), status_code)

        if data is None:
            return better_json(ErrorResponse(ErrorCode.MIHOMO_UID_NOT_FOUND, "Invalid UID provided"), 404)

        try:
            character_sel = data.characters[character - 1]
        except IndexError:
            return better_json(ErrorResponse(ErrorCode.MIHOMO_INVALID_CHARACTER, "Invalid character"), 400)

        filename = f"{uid}_{character_sel.id}_Card{q_lang.name}.Qingque.png"
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

        # Cache response for 3 minutes
        if token is not None:
            self.logger.info(f"Setting cache for: {token} (with key: {cache_key})")
            await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)
        # Results is PNG bytes
        return self._make_response(filename, results)

    @get("/player.png")
    @docs(
        summary="Create a Mihomo player card",
        description="Generate a Mihomo player card either from provided token or provided UID.",
        tags=["Mihomo"],
        responses=_mihomo_resp_info,
    )
    async def create_player_card(
        self,
        uid: int | None = None,
        token: str | None = None,
        lang: str = "en-US",
    ):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        if uid is None and token is None:
            return better_json(ErrorResponse(ErrorCode.MISSING_UID_TOKEN, "Missing uid or token"), 400)

        cache_key = TransactionCacheKind.make(TransactionCacheKind.MIHOMO_PLAYER, q_lang.name)
        data: Player | None = None
        if token is not None:
            self.logger.info(f"Checking cache for: {token}")
            cached = await self.transactions.get(token, type=TransactionMihomo)
            img_cache = await self.transactions.get_gen_cache(token, cache_type=cache_key)
            if cached is None and img_cache is not None:
                self.logger.info(f"Found cache for: {token}")
                return self._make_response(f"PlayerCard{q_lang.name}_{token}.Qingque.png", img_cache)
            if cached is not None and img_cache is not None:
                self.logger.info(f"Found cache for: {token}")
                return self._make_response(f"PlayerCard{q_lang.name}_{cached.uid}.Qingque.png", img_cache)
            if cached is None:
                return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)
            uid = cached.uid
            data = cached.cached

        self.logger.info(f"Generating player card for {uid}...")
        if token is not None:
            self.logger.info(f"Using token {token}")

        if uid is not None and data is None:
            try:
                data, _ = await self.mihomo.get_player(uid)
            except aiohttp.ClientResponseError as e:
                status_code = 503 if e.status != 404 else 404
                error_code = ErrorCode.MIHOMO_ERROR if e.status != 404 else ErrorCode.MIHOMO_UID_NOT_FOUND
                error_ = f"Unable to get Mihomo data for {uid}: {e.message} ({e.status})"
                return better_json(ErrorResponse(error_code, error_), status_code)

        if data is None:
            return better_json(ErrorResponse(ErrorCode.MIHOMO_UID_NOT_FOUND, "Invalid UID provided"), 404)

        filename = f"PlayerCard{q_lang.name}_{uid}.Qingque.png"
        mihomo_gen = StarRailPlayerCard(
            player=data,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        results = await mihomo_gen.create(clear_cache=False)

        if token is not None:
            self.logger.info(f"Setting cache for: {token} ({cache_key})")
            await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)

        # Cache response for 10 minutes
        # Results is PNG bytes
        return self._make_response(filename, results, ttl=600)
