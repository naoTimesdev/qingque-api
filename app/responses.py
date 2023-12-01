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

import msgspec
import orjson
from blacksheep import Content, Response
from msgspec import Struct

__all__ = (
    "ErrorResponse",
    "better_json",
    "better_pretty_json",
)


@dataclass
class ErrorResponse:
    code: int
    message: str
    data: Any | None = None


def dumps_json(obj: Any) -> bytes:
    if isinstance(obj, Struct):
        return msgspec.json.encode(obj)
    return orjson.dumps(obj)


def pretty_dumps_json(obj: Any) -> bytes:
    if isinstance(obj, Struct):
        return msgspec.json.format(msgspec.json.encode(obj), indent=2)
    return orjson.dumps(obj, option=orjson.OPT_INDENT_2)


def better_json(
    data: Any,
    status: int = 200,
) -> Response:
    """Return a JSON response with the given data and status code."""

    return Response(
        status,
        None,
        Content(
            b"application/json",
            dumps_json(data),
        ),
    )


def better_pretty_json(
    data: Any,
    status: int = 200,
) -> Response:
    """Return a JSON response with the given data and status code."""

    return Response(
        status,
        None,
        Content(
            b"application/json",
            pretty_dumps_json(data),
        ),
    )
