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

from typing import Any

from blacksheep import Request, Response
from blacksheep.server import Application
from blacksheep.server.responses import text
from essentials.exceptions import (
    AcceptedException,
    ForbiddenException,
    NotImplementedException,
    ObjectNotFound,
    UnauthorizedException,
)


def configure_error_handlers(app: Application) -> None:
    async def not_found_handler(app: Application, request: Request, exception: Exception) -> Response:
        return text(str(exception) or "Not found", 404)

    async def not_implemented(*args: Any) -> Response:
        return text("Not implemented", status=500)

    async def unauthorized(*args: Any) -> Response:
        return text("Unauthorized", status=401)

    async def forbidden(*args: Any) -> Response:
        return text("Forbidden", status=403)

    async def accepted(*args: Any) -> Response:
        return text("Accepted", status=202)

    app.exceptions_handlers.update(
        {
            ObjectNotFound: not_found_handler,
            NotImplementedException: not_implemented,
            UnauthorizedException: unauthorized,
            ForbiddenException: forbidden,
            AcceptedException: accepted,
        }
    )
