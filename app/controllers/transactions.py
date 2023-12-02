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
from blacksheep.server.openapi.common import ContentInfo, ResponseExample, ResponseInfo

from app.docs import docs
from app.responses import ErrorCode, ErrorResponse, better_json
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


_token_created_resp = ResponseInfo(
    "Token created",
    content=[
        ContentInfo(
            ErrorResponse,
            examples=[
                ResponseExample(
                    ErrorResponse(
                        code=ErrorCode.SUCCESS,
                        message="Success",
                        data="abcdefghijklkmnopqrstuvwxyz1234567890",
                    )
                )
            ],
        )
    ],
)


def make_docs(transact_type: str):
    return docs(
        summary=f"Create a new transactions for {transact_type}",
        tags=["Transactions"],
        responses={
            400: ResponseInfo(
                f"Failed to verify {transact_type} credentials",
                content=[
                    ContentInfo(
                        ErrorResponse,
                        examples=[
                            ResponseExample(
                                ErrorResponse(
                                    ErrorCode.TR_FAILED_VERIFICATION,
                                    f"Error when testing {transact_type} credentials: 401 Unauthorized (401)",
                                ),
                            )
                        ],
                    )
                ],
            ),
            200: _token_created_resp,
        },
    )


class Transactions(Controller):
    def __init__(
        self, settings: Settings, mihomo: MihomoAPI, hylab: HYLabClient, transactions: TransactionsHelper
    ) -> None:
        self.settings = settings
        self.mihomo = mihomo
        self.hylab = hylab
        self.transactions = transactions

    @classmethod
    def route(cls) -> str | None:
        return "/api/exchange"

    @post("/hoyolab")
    @make_docs("HoyoLab")
    async def create_transactions_hoyolab(self, data: FromJSON[HYLabTransactInput]):
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
            return better_json(ErrorResponse(ErrorCode.TR_FAILED_VERIFICATION, error_), status=400)

        transact = TransactionHoyolab(
            uid=value.uid,
            ltuid=value.ltuid,
            ltoken=value.ltoken,
            lcookie=value.lcookie,
            lmid=value.lmid,
        )
        token = await self.transactions.create(transact, ttl=self.settings.app.transaction_ttl)

        return better_json(ErrorResponse(ErrorCode.SUCCESS, "Success", token))

    @post("/mihomo")
    @make_docs("Mihomo")
    async def create_transactions_mihomo(self, data: FromJSON[MihomoTransactInput]):
        value = data.value

        try:
            player_data, _ = await self.mihomo.get_player(value.uid)
        except aiohttp.ClientResponseError as e:
            error_ = f"Error when testing Mihomo credentials: {e.message} ({e.status})"
            return better_json(ErrorResponse(ErrorCode.TR_FAILED_VERIFICATION, error_), status=400)

        transact = TransactionMihomo(
            uid=value.uid,
            cached=player_data,
        )
        token = await self.transactions.create(transact, ttl=self.settings.app.mihomo_ttl)

        return better_json(ErrorResponse(ErrorCode.SUCCESS, "Success", token))
