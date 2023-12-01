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
from typing import Optional

import aiohttp
from blacksheep import FromJSON
from blacksheep.server.controllers import Controller, post

from app.responses import ErrorResponse, better_json
from app.settings import Settings
from domain.hylab.client import HYLabClient
from domain.hylab.models.errors import HYLabException
from domain.mihomo.client import MihomoAPI
from domain.transcations import TransactionHoyolab, TransactionMihomo, TransactionsHelper


@dataclass
class MihomoTransactInput:
    uid: int


@dataclass
class HYLabTransactInput:
    uid: int
    ltuid: int
    ltoken: str
    lcookie: Optional[str] = None
    lmid: Optional[str] = None


class HoyolabTransactionController(Controller):
    def __init__(self, settings: Settings, hylab: HYLabClient, transactions: TransactionsHelper) -> None:
        self.settings = settings
        self.hylab = hylab
        self.transactions = transactions

    @classmethod
    def route(cls) -> str | None:
        return "/api/exchange/hoyolab"

    @classmethod
    def class_name(cls) -> str:
        return "Transaction"

    @post()
    async def create_transactions(self, data: FromJSON[HYLabTransactInput]):
        value = data.value

        try:
            await self.hylab.get_battle_chronicles_basic_info(
                uid=value.uid,
                hylab_id=value.ltuid,
                hylab_token=value.ltoken,
                hylab_cookie=value.lcookie,
                hylab_mid_token=value.lmid,
            )
        except HYLabException as e:
            error_ = f"Error when testing HoyoLab credentials: {e.msg} ({e.retcode})"
            return better_json(ErrorResponse(400, error_), status=400)

        transact = TransactionHoyolab(
            uid=value.uid,
            ltuid=value.ltuid,
            ltoken=value.ltoken,
            lcookie=value.lcookie,
            lmid=value.lmid,
        )
        token = await self.transactions.create(transact, ttl=self.settings.app.transaction_ttl)

        return better_json(ErrorResponse(200, "Success", token))


class MihomoTransactionController(Controller):
    def __init__(self, settings: Settings, mihomo: MihomoAPI, transactions: TransactionsHelper) -> None:
        self.settings = settings
        self.mihomo = mihomo
        self.transactions = transactions

    @classmethod
    def route(cls) -> str | None:
        return "/api/exchange/mihomo"

    @classmethod
    def class_name(cls) -> str:
        return "Transaction"

    @post()
    async def create_transactions(self, data: FromJSON[MihomoTransactInput]):
        value = data.value

        try:
            player_data, _ = await self.mihomo.get_player(value.uid)
        except aiohttp.ClientResponseError as e:
            error_ = f"Error when testing Mihomo credentials: {e.message} ({e.status})"
            return better_json(ErrorResponse(400, error_), status=400)

        transact = TransactionMihomo(
            uid=value.uid,
            cached=player_data,
        )
        token = await self.transactions.create(transact, ttl=self.settings.app.mihomo_ttl)

        return better_json(ErrorResponse(200, "Success", token))
