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

from enum import Enum
from typing import Any, TypeVar, cast

from blacksheep import Content, Response
from blacksheep.server.controllers import Controller, get
from msgspec import Struct

from app.docs import docs
from app.responses import ErrorCode, ErrorResponse, better_json
from app.settings import Settings
from domain.hylab.client import HYLabClient
from domain.hylab.models.base import HYLanguage
from domain.hylab.models.characters import ChronicleCharacters
from domain.hylab.models.errors import HYAccountNotFound, HYDataNotPublic, HYInvalidCookies, HYLabException
from domain.hylab.models.forgotten_hall import ChronicleForgottenHall
from domain.hylab.models.notes import ChronicleNotes
from domain.hylab.models.overview import ChronicleUserInfo, ChronicleUserOverview
from domain.hylab.models.simuniverse import ChronicleSimulatedUniverse, ChronicleSimulatedUniverseSwarmDLC
from domain.i18n import QingqueI18n, QingqueLanguage
from domain.starrail.caching import StarRailImageCache
from domain.starrail.generator.characters import StarRailCharactersCard
from domain.starrail.generator.chronicles import StarRailChronicleNotesCard
from domain.starrail.generator.moc import StarRailMoCCard
from domain.starrail.generator.simuniverse import StarRailSimulatedUniverseCard
from domain.starrail.loader import SRSDataLoaderI18n
from domain.transcations import TransactionCacheKind, TransactionHoyolab, TransactionsHelper
from qutils.tooling import get_logger

_ERROR_MAPS = {
    HYDataNotPublic: ErrorResponse(ErrorCode.HOYOLAB_DATA_NOT_PUBLIC, "Data is not public"),
    HYAccountNotFound: ErrorResponse(ErrorCode.HOYOLAB_ACCOUNT_NOT_FOUND, "Account not found"),
    HYInvalidCookies: ErrorResponse(ErrorCode.HOYOLAB_INVALID_COOKIES, "Invalid cookies/token"),
}
HoyoT = TypeVar("HoyoT", bound=Struct)


class HYSimUniverseKind(str, Enum):
    Current = "current"
    Previous = "previous"
    SwarmDisaster = "swarm"


class HYMoCKind(str, Enum):
    Current = "current"
    Previous = "previous"


class HoyoLab(Controller):
    def __init__(
        self,
        settings: Settings,
        hoyolab: HYLabClient,
        transactions: TransactionsHelper,
        i18n: QingqueI18n,
        srs_cache: StarRailImageCache,
        srs_i18n: SRSDataLoaderI18n,
    ) -> None:
        self.i18n = i18n
        self.srs_cache = srs_cache
        self.srs_i18n = srs_i18n
        self.settings = settings
        self.hoyoapi = hoyolab
        self.transactions = transactions

        self.logger = get_logger("qingque.api.controllers.hoyolab")

    @classmethod
    def route(cls) -> str | None:
        return "/api/hoyolab"

    async def _wrap_hoyo_call(self, func, *args, **kwargs) -> Any | HYLabException | Exception:
        try:
            return await func(*args, **kwargs)
        except (HYDataNotPublic, HYAccountNotFound, HYInvalidCookies) as hye:
            return hye
        except Exception as e:
            self.logger.error("Error while calling HoyoLab API", exc_info=e)
            return e

    def _make_cache_key(self, kind: str, transact: TransactionHoyolab, suffix: str = ""):
        suffix = f":{suffix}" if suffix else ""
        return TransactionCacheKind.make(kind, f"{transact.uid}:{transact.ltuid}{suffix}")

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

    @get("/chronicles")
    @docs(
        summary="Create a overview card for a user",
        description="Generate a overview card for a user from Hoyolab data, you would need to exchange token first!",
        tags=["HoyoLab"],
    )
    async def create_chronicles_card(self, token: str, lang: str = "en-US", nocache: bool = False):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        cached = await self.transactions.get(token, type=TransactionHoyolab)
        if cached is None:
            return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)

        card_filename = f"Chronicles_{cached.uid}_Overview{q_lang.name}.Qingque.png"
        cache_key = self._make_cache_key(TransactionCacheKind.HY_CHRONICLES, cached, f"overview:{q_lang.value}")
        if not nocache:
            self.logger.info(f"Checking for cached card for UID: {cached.uid} ({cache_key})")
            cached_card = await self.transactions.get_gen_cache(token, cache_key)
            if cached_card is not None:
                self.logger.info(f"Found cached card for UID: {cached.uid} ({cache_key})")
                return self._make_response(card_filename, cached_card)

        self.logger.info(f"Getting profile overview for UID: {cached.uid}")
        hoyo_overview = await self._wrap_hoyo_call(
            self.hoyoapi.get_battle_chronicles_overview,
            cached.uid,
            hylab_id=cached.ltuid,
            hylab_token=cached.ltoken,
            hylab_mid_token=cached.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_overview, HYLabException):
            self.logger.error(f"Error while getting profile overview for UID: {cached.uid}", exc_info=hoyo_overview)
            default_error = ErrorResponse(
                ErrorCode.HOYOLAB_ERROR, f"Error while getting profile overview: {hoyo_overview}"
            )
            error_data = _ERROR_MAPS.get(type(hoyo_overview), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_overview, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_overview}")
            return better_json(error_data, 500)

        hoyo_overview = cast(ChronicleUserOverview | None, hoyo_overview)
        if hoyo_overview is None:
            self.logger.error(f"Invalid profile overview for UID: {cached.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable"), 500)
        if hoyo_overview.overview is None:
            self.logger.error(f"Invalid profile overview for UID: {cached.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable (missing overview)"), 500)
        if hoyo_overview.user_info is None:
            self.logger.error(f"Invalid profile overview for UID: {cached.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable (missing user info)"), 500)

        self.logger.info(f"Getting profile real-time notes for UID: {cached.uid}")
        hoyo_notes = await self._wrap_hoyo_call(
            self.hoyoapi.get_battle_chronicles_notes,
            cached.uid,
            hylab_id=cached.ltuid,
            hylab_token=cached.ltoken,
            hylab_mid_token=cached.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_notes, HYLabException):
            self.logger.error(f"Error while getting real-time notes for UID: {cached.uid}", exc_info=hoyo_notes)
            default_error = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"Error while getting real-time notes: {hoyo_notes}")
            error_data = _ERROR_MAPS.get(type(hoyo_notes), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_notes, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_notes}")
            return better_json(error_data, 500)

        hoyo_notes = cast(ChronicleNotes | None, hoyo_notes)
        if hoyo_notes is None:
            self.logger.error(f"Invalid real-time notes for UID: {cached.uid}")
            return better_json(
                ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable (real-time notes is unavailable)"), 500
            )

        card_gen = StarRailChronicleNotesCard(
            overview=hoyo_overview,
            chronicle=hoyo_notes,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        self.logger.info(f"Generating card for UID: {cached.uid}")
        results = await card_gen.create(hide_credits=True, clear_cache=False)
        self.logger.info(f"Setting cache for UID: {cached.uid} ({cache_key})")

        await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)
        return self._make_response(card_filename, results)

    @get("/characters")
    @docs(
        summary="Create a characters list card for a user",
        description=(
            "Generate a characters list card for a user from Hoyolab data, you would need to exchange token first!"
        ),
        tags=["HoyoLab"],
    )
    async def create_chronicles_characters(self, token: str, lang: str = "en-US", nocache: bool = False):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        cached = await self.transactions.get(token, type=TransactionHoyolab)
        if cached is None:
            return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)

        card_filename = f"Chronicles_{cached.uid}_Characters{q_lang.name}.Qingque.png"
        cache_key = self._make_cache_key(TransactionCacheKind.HY_CHRONICLES, cached, f"characters:{q_lang.value}")
        if not nocache:
            self.logger.info(f"Checking for cached card for UID: {cached.uid} ({cache_key})")
            cached_card = await self.transactions.get_gen_cache(token, cache_key)
            if cached_card is not None:
                self.logger.info(f"Found cached card for UID: {cached.uid} ({cache_key})")
                return self._make_response(card_filename, cached_card)

        self.logger.info(f"Getting profile info for UID: {cached.uid}")
        hoyo_user_info = await self._wrap_hoyo_call(
            self.hoyoapi.get_battle_chronicles_basic_info,
            cached.uid,
            hylab_id=cached.ltuid,
            hylab_token=cached.ltoken,
            hylab_mid_token=cached.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_user_info, HYLabException):
            self.logger.error(f"Error while getting profile info for UID: {cached.uid}", exc_info=hoyo_user_info)
            default_error = ErrorResponse(
                ErrorCode.HOYOLAB_ERROR, f"Error while getting profile overview: {hoyo_user_info}"
            )
            error_data = _ERROR_MAPS.get(type(hoyo_user_info), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_user_info, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_user_info}")
            return better_json(error_data, 500)

        hoyo_user_info = cast(ChronicleUserInfo | None, hoyo_user_info)
        if hoyo_user_info is None:
            self.logger.error(f"Invalid profile info for UID: {cached.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable"), 500)

        self.logger.info(f"Getting profile characters for UID: {cached.uid}")
        hoyo_characters = await self._wrap_hoyo_call(
            self.hoyoapi.get_battle_chronicles_characters,
            cached.uid,
            hylab_id=cached.ltuid,
            hylab_token=cached.ltoken,
            hylab_mid_token=cached.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_characters, HYLabException):
            self.logger.error(f"Error while getting profile characters for UID: {cached.uid}", exc_info=hoyo_characters)
            default_error = ErrorResponse(
                ErrorCode.HOYOLAB_ERROR, f"Error while getting profile characters: {hoyo_characters}"
            )
            error_data = _ERROR_MAPS.get(type(hoyo_characters), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_characters, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_characters}")
            return better_json(error_data, 500)

        hoyo_characters = cast(ChronicleCharacters | None, hoyo_characters)
        if hoyo_characters is None:
            self.logger.error(f"Invalid profile characters for UID: {cached.uid}")
            return better_json(
                ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable (profile characters is unavailable)"), 500
            )

        card_gen = StarRailCharactersCard(
            user_info=hoyo_user_info,
            characters=hoyo_characters,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        self.logger.info(f"Generating card for UID: {cached.uid}")
        results = await card_gen.create(hide_credits=True, clear_cache=False)
        self.logger.info(f"Setting cache for UID: {cached.uid} ({cache_key})")

        await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)
        return self._make_response(card_filename, results)

    async def _fetch_simulated_universe(
        self, func, transact: TransactionHoyolab, q_lang: QingqueLanguage
    ) -> Response | ChronicleSimulatedUniverse | ChronicleSimulatedUniverseSwarmDLC:
        hoyo_simuniverse = await self._wrap_hoyo_call(
            func,
            transact.uid,
            hylab_id=transact.ltuid,
            hylab_token=transact.ltoken,
            hylab_mid_token=transact.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_simuniverse, HYLabException):
            self.logger.error(
                f"Error while getting sim universe data for UID: {transact.uid}", exc_info=hoyo_simuniverse
            )
            default_error = ErrorResponse(
                ErrorCode.HOYOLAB_ERROR, f"Error while getting simulated universe: {hoyo_simuniverse}"
            )
            error_data = _ERROR_MAPS.get(type(hoyo_simuniverse), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_simuniverse, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_simuniverse}")
            return better_json(error_data, 500)

        hoyo_simuniverse = cast(
            ChronicleSimulatedUniverse | ChronicleSimulatedUniverseSwarmDLC | None, hoyo_simuniverse
        )
        if hoyo_simuniverse is None:
            self.logger.error(f"Invalid profile info for UID: {transact.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable"), 500)
        return hoyo_simuniverse

    @get("/simuniverse/{str:kind}/{int:index}")
    @docs(
        summary="Create a simulated universe card for a user",
        description=(
            "Generate a simulated universe card for a user from Hoyolab data, you would need to exchange token first!"
        ),
        tags=["HoyoLab"],
    )
    async def create_chronicles_simuniverse(
        self, kind: str, index: int, token: str, lang: str = "en-US", nocache: bool = False
    ):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        try:
            q_kind = HYSimUniverseKind(kind)
        except ValueError:
            return better_json(
                ErrorResponse(
                    ErrorCode.HOYOLAB_SIMU_UNKNOWN_KIND, f"Invalid kind: {kind} (must be: current/previous/swarm)"
                ),
                400,
            )

        if index < 1:
            return better_json(
                ErrorResponse(ErrorCode.INVALID_INDEX, "Invalid index provided, must be more than 1"), 400
            )

        cached = await self.transactions.get(token, type=TransactionHoyolab)
        if cached is None:
            return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)

        card_filename = f"Chronicles_{cached.uid}_SimUniverse{q_kind.name}_{index}_{q_lang.name}.Qingque.png"
        cache_key = self._make_cache_key(
            TransactionCacheKind.HY_SIMUNIVERSE, cached, f"{q_kind.value}:INDEX_{index}:{q_lang.value}"
        )
        if not nocache:
            self.logger.info(f"Checking for cached card for UID: {cached.uid} ({cache_key})")
            cached_card = await self.transactions.get_gen_cache(token, cache_key)
            if cached_card is not None:
                self.logger.info(f"Found cached card for UID: {cached.uid} ({cache_key})")
                return self._make_response(card_filename, cached_card)

        index -= 1

        swarm_striders = None
        if q_kind is HYSimUniverseKind.SwarmDisaster:
            self.logger.info(f"Getting simulated universe swarm disaster for UID: {cached.uid}")
            hoyo_simuniverse = await self._fetch_simulated_universe(
                self.hoyoapi.get_battle_chronicles_simulated_universe_swarm_dlc,
                transact=cached,
                q_lang=q_lang,
            )
            if isinstance(hoyo_simuniverse, Response):
                return hoyo_simuniverse
            hoyo_simuniverse = cast(ChronicleSimulatedUniverseSwarmDLC, hoyo_simuniverse)
            if not hoyo_simuniverse.details.records:
                return better_json(
                    ErrorResponse(ErrorCode.HOYOLAB_SIMU_NO_RECORDS, "No records found for this user"), 400
                )
            try:
                record = hoyo_simuniverse.details.records[index]
            except IndexError:
                return better_json(
                    ErrorResponse(ErrorCode.HOYOLAB_SIMU_INVALID_INDEX, "Invalid index provided, out of range"), 400
                )
            swarm_striders = hoyo_simuniverse.overview.destiny
        else:
            self.logger.info(f"Getting simulated universe for UID: {cached.uid}")
            hoyo_simuniverse = await self._fetch_simulated_universe(
                self.hoyoapi.get_battle_chronicles_simulated_universe,
                transact=cached,
                q_lang=q_lang,
            )
            if isinstance(hoyo_simuniverse, Response):
                return hoyo_simuniverse
            hoyo_simuniverse = cast(ChronicleSimulatedUniverse, hoyo_simuniverse)
            try:
                records = hoyo_simuniverse.current if q_kind is HYSimUniverseKind.Current else hoyo_simuniverse.previous
                if not records.records:
                    return better_json(
                        ErrorResponse(ErrorCode.HOYOLAB_SIMU_NO_RECORDS, "No records found for this user"), 400
                    )
                record = records.records[index]
            except IndexError:
                return better_json(
                    ErrorResponse(ErrorCode.HOYOLAB_SIMU_INVALID_INDEX, "Invalid index provided, out of range"), 400
                )

        card_gen = StarRailSimulatedUniverseCard(
            user=hoyo_simuniverse.user,
            record=record,
            swarm_striders=swarm_striders,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        self.logger.info(f"Generating card for UID: {cached.uid}")
        results = await card_gen.create(hide_credits=True, clear_cache=False)
        self.logger.info(f"Setting cache for UID: {cached.uid} ({cache_key})")

        await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)
        return self._make_response(card_filename, results)

    @get("/moc/{str:kind}/{int:floor}")
    @docs(
        summary="Create a memory of chaos card for a user",
        description=(
            "Generate a memory of chaos card for a user from Hoyolab data, you would need to exchange token first!"
        ),
        tags=["HoyoLab"],
    )
    async def create_chronicles_moc(
        self, kind: str, floor: int, token: str, lang: str = "en-US", nocache: bool = False
    ):
        try:
            q_lang = QingqueLanguage(lang)
        except ValueError:
            return better_json(ErrorResponse(ErrorCode.INVALID_LANG, f"Invalid language: {lang}"), 400)

        try:
            q_kind = HYMoCKind(kind)
        except ValueError:
            return better_json(
                ErrorResponse(ErrorCode.HOYOLAB_SIMU_UNKNOWN_KIND, f"Invalid kind: {kind} (must be: current/previous)"),
                400,
            )

        if floor < 1:
            return better_json(
                ErrorResponse(ErrorCode.INVALID_INDEX, "Invalid index provided, must be more than 1"), 400
            )

        cached = await self.transactions.get(token, type=TransactionHoyolab)
        if cached is None:
            return better_json(ErrorResponse(ErrorCode.TR_INVALID_TOKEN, "Invalid token provided"), 403)

        card_filename = f"Chronicles_{cached.uid}_MoC{q_kind.name}_F{floor}_{q_lang.name}.Qingque.png"
        cache_key = self._make_cache_key(
            TransactionCacheKind.HY_MOC, cached, f"{q_kind.value}:FLOOR_{floor}:{q_lang.value}"
        )
        if not nocache:
            self.logger.info(f"Checking for cached card for UID: {cached.uid} ({cache_key})")
            cached_card = await self.transactions.get_gen_cache(token, cache_key)
            if cached_card is not None:
                self.logger.info(f"Found cached card for UID: {cached.uid} ({cache_key})")
                return self._make_response(card_filename, cached_card)

        self.logger.info(f"Getting profile forgotten hall for UID: {cached.uid} ({q_kind.value} state)")
        hoyo_moc = await self._wrap_hoyo_call(
            self.hoyoapi.get_battle_chronicles_forgotten_hall,
            cached.uid,
            previous=q_kind is HYMoCKind.Previous,
            hylab_id=cached.ltuid,
            hylab_token=cached.ltoken,
            hylab_mid_token=cached.lmid,
            lang=HYLanguage(q_lang.value.lower()),
        )
        if isinstance(hoyo_moc, HYLabException):
            self.logger.error(
                f"Error while getting profile forgotten hall ({q_kind.value}) for UID: {cached.uid}", exc_info=hoyo_moc
            )
            default_error = ErrorResponse(
                ErrorCode.HOYOLAB_ERROR, f"Error while getting profile forgotten hall ({q_kind.value}): {hoyo_moc}"
            )
            error_data = _ERROR_MAPS.get(type(hoyo_moc), default_error)  # type: ignore
            return better_json(error_data, 500)
        if isinstance(hoyo_moc, Exception):
            error_data = ErrorResponse(ErrorCode.HOYOLAB_ERROR, f"An error occurred: {hoyo_moc}")
            return better_json(error_data, 500)

        hoyo_moc = cast(ChronicleForgottenHall | None, hoyo_moc)
        if hoyo_moc is None:
            self.logger.error(f"Invalid profile characters for UID: {cached.uid}")
            return better_json(ErrorResponse(ErrorCode.HOYOLAB_ERROR, "Data is unavailable"), 500)

        # Floor order is reversed, it would be easier to just reverse the floor number (or index)
        # Since the data from API is frozen.
        floor = len(hoyo_moc.floors) - floor

        try:
            floor_data = hoyo_moc.floors[floor]
        except IndexError:
            return better_json(
                ErrorResponse(
                    ErrorCode.HOYOLAB_SIMU_INVALID_INDEX,
                    f"Invalid index provided, out of range: {len(hoyo_moc.floors)} floor available",
                ),
                400,
            )

        card_gen = StarRailMoCCard(
            floor=floor_data,
            i18n=self.i18n,
            language=q_lang,
            loader=self.srs_i18n.get(q_lang),
            img_cache=self.srs_cache,
        )

        self.logger.info(f"Generating card for UID: {cached.uid}")
        results = await card_gen.create(hide_credits=True, clear_cache=False)
        self.logger.info(f"Setting cache for UID: {cached.uid} ({cache_key})")

        await self.transactions.set_gen_cache(token, cache_key, results, ttl=self.settings.app.image_ttl)
        return self._make_response(card_filename, results)
