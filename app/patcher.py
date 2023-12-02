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

import essentials.json
import msgspec
import orjson
from msgspec import Struct

from qutils.tooling import get_logger

__all__ = (
    "run_monkeypatch",
    "monkeypatch_essentials_friendlyjson",
)
logger = get_logger("qingque.api.patcher")


def monkeypatch_essentials_friendlyjson():
    FriendlyEncoder = essentials.json.FriendlyEncoder

    class FriendlierEncoder(FriendlyEncoder):
        def default(self, obj):
            try:
                return super().default(obj)
            except TypeError:
                if isinstance(obj, Struct):
                    return orjson.loads(msgspec.json.encode(obj))
                raise

    logger.info("Patching essentials.json.FriendlyEncoder...")
    essentials.json.FriendlyEncoder = FriendlierEncoder


def run_monkeypatch():
    monkeypatch_essentials_friendlyjson()
