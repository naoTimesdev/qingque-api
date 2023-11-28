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

import logging
from enum import Enum
from pathlib import Path
from string import Formatter
from typing import Any, Protocol, cast

import orjson

from domain.mihomo.models.constants import MihomoLanguage
from qutils.utils import complex_walk

__all__ = (
    "QingqueLanguage",
    "QingqueI18n",
    "PartialTranslate",
    "get_roman_numeral",
)

logger = logging.getLogger("qingque.i18n")


class QingqueLanguage(str, Enum):
    CHT = "zh-TW"
    CHS = "zh-CN"
    DE = "de-DE"
    EN = "en-US"
    ES = "es-ES"
    FR = "fr-FR"
    ID = "id-ID"
    JP = "ja-JP"
    KR = "ko-KR"
    PT = "pt-PT"
    RU = "ru-RU"
    TH = "th-TH"
    VI = "vi-VN"

    def to_mihomo(self) -> MihomoLanguage:
        name = self.name.lower()
        if name == "chs":
            name = "cn"
        if name == "it":
            name = "en"
        return MihomoLanguage(name)

    @classmethod
    def from_mihomo(cls: type[QingqueLanguage], lang: MihomoLanguage) -> QingqueLanguage:
        match lang:
            case MihomoLanguage.CHT:
                return cls.CHT
            case MihomoLanguage.CHS:
                return cls.CHS
            case MihomoLanguage.DE:
                return cls.DE
            case MihomoLanguage.EN:
                return cls.EN
            case MihomoLanguage.ES:
                return cls.ES
            case MihomoLanguage.FR:
                return cls.FR
            case MihomoLanguage.ID:
                return cls.ID
            case MihomoLanguage.JP:
                return cls.JP
            case MihomoLanguage.KR:
                return cls.KR
            case MihomoLanguage.PT:
                return cls.PT
            case MihomoLanguage.RU:
                return cls.RU
            case MihomoLanguage.TH:
                return cls.TH
            case MihomoLanguage.VI:
                return cls.VI
            case _:
                raise ValueError(f"Unknown language {lang!r}.")


KVI18n = dict[str, str]
KVI18nDict = dict[str, KVI18n | str]


class _OptinalDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class OptionalFormatter:
    def __init__(self, data: dict[str, Any]) -> None:
        self.fmt = Formatter()
        self.data = _OptinalDict(data)

    @classmethod
    def format(cls, text: str, *args: Any, **kwargs: Any) -> str:
        formatter = cls(kwargs)
        return formatter.fmt.vformat(text, args, formatter.data)


class QingqueI18nLoader:
    _DEFAULT = QingqueLanguage.EN
    _LOCALES_DATA: dict[QingqueLanguage, KVI18nDict]

    def __init__(self) -> None:
        self._LOCALES_DATA = {}

    def _get_from_lang(self, key: str, language: QingqueLanguage | str) -> str | None:
        if isinstance(language, str):
            language = QingqueLanguage(language)
        if language not in self._LOCALES_DATA:
            return None
        locale = self._LOCALES_DATA[language]
        translation = complex_walk(locale, key)
        return cast(str | None, translation)

    def _fmt_tl(self, text: str, params: list[str] | dict[str, str] | None = None) -> str:
        if params is not None:
            if isinstance(params, list):
                return OptionalFormatter.format(text, *params)
            return OptionalFormatter.format(text, **params)
        return text

    def t(
        self,
        key: str,
        params: list[str] | dict[str, str] | None = None,
        *,
        language: QingqueLanguage | str | None = None,
    ) -> str:
        language = language or self._DEFAULT
        translation = self._get_from_lang(key, language)
        if translation is None:
            logger.debug(f"Translation for {key} in {language} is not found, fallback to {self._DEFAULT.name}")
            translation = self._get_from_lang(key, self._DEFAULT)
            if translation is None:
                logger.debug(f"Translation for {key} in {self._DEFAULT.name} is not found, fallback to raw key")
                return key

        return self._fmt_tl(translation, params)

    def load(self, language: QingqueLanguage, data: KVI18nDict) -> None:
        # Merge the data
        self._LOCALES_DATA.setdefault(language, {}).update(data)

    def copy(self, default: QingqueLanguage | None = None) -> QingqueI18nLoader:
        new = QingqueI18nLoader()
        new._LOCALES_DATA = self._LOCALES_DATA.copy()
        new._DEFAULT = default or self._DEFAULT
        return new


class PartialTranslate(Protocol):
    def __call__(self, key: str, params: list[str] | dict[str, str] | None = ...) -> str:
        ...


_LATIN_NUMERALS = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
    5: "V",
    6: "VI",
    7: "VII",
    8: "VIII",
    9: "IX",
    10: "X",
}
_CHINESE_NUMERALS = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
}
_CHINESE_TAIWAN_NUMERALS = {
    1: "壹",
    2: "貳",
    3: "參",
    4: "肆",
    5: "伍",
    6: "陸",
    7: "柒",
    8: "捌",
    9: "玖",
    10: "拾",
}
_KOREAN_NUMERALS = {
    1: "일",
    2: "이",
    3: "삼",
    4: "사",
    5: "오",
    6: "육",
    7: "칠",
    8: "팔",
    9: "구",
    10: "십",
}
_CYRILLIC_NUMERALS = {
    1: "А",  # noqa: RUF001
    2: "Б",
    3: "Г",
    4: "Д",
    5: "Е",  # noqa: RUF001
    6: "Ѕ",  # noqa: RUF001
    7: "З",  # noqa: RUF001
    8: "И",
    9: "І",  # noqa: RUF001
    10: "І",  # noqa: RUF001
}
_THAI_NUMERALS = {
    1: "๑",
    2: "๒",
    3: "๓",
    4: "๔",
    5: "๕",
    6: "๖",
    7: "๗",
    8: "๘",
    9: "๙",
    10: "๑๐",
}


def get_roman_numeral(n: int, /, *, lang: QingqueLanguage | MihomoLanguage = QingqueLanguage.EN) -> str:
    if isinstance(lang, MihomoLanguage):
        lang = QingqueLanguage.from_mihomo(lang)
    fallback = _LATIN_NUMERALS.get(n, str(n))
    match lang:
        case QingqueLanguage.JP | QingqueLanguage.CHS:
            return _CHINESE_NUMERALS.get(n, fallback)
        case QingqueLanguage.CHT:
            return _CHINESE_TAIWAN_NUMERALS.get(n, fallback)
        case QingqueLanguage.KR:
            return _KOREAN_NUMERALS.get(n, fallback)
        case QingqueLanguage.RU:
            return _CYRILLIC_NUMERALS.get(n, fallback)
        case QingqueLanguage.TH:
            return _THAI_NUMERALS.get(n, fallback)
        case _:
            return fallback


class QingqueI18n(QingqueI18nLoader):
    def __init__(self, i18n_path: Path, *, skip_autoload: bool = False) -> None:
        super().__init__()

        self._i18n_path = i18n_path

        if not skip_autoload:
            self.autoload()

    def autoload(self) -> None:
        for language_dir in self._i18n_path.iterdir():
            if not language_dir.is_dir():
                continue
            language = QingqueLanguage(language_dir.stem)
            logger.debug(f"Loading language {language.name}...")
            for file in language_dir.iterdir():
                if file.suffix in [".json", "json"]:
                    logger.debug(f"-- Loading file {file.name}...")
                    json_data = orjson.loads(file.read_bytes())
                    self.load(language, cast(KVI18nDict, json_data))

    def troman(self, n: int, *, lang: QingqueLanguage | MihomoLanguage | None = None) -> str:
        return get_roman_numeral(n, lang=lang or self._DEFAULT)

    def copy(self, default: QingqueLanguage | None = None) -> QingqueI18n:
        new = QingqueI18n(self._i18n_path, skip_autoload=True)
        new._LOCALES_DATA = self._LOCALES_DATA.copy()
        new._DEFAULT = default or self._DEFAULT
        return new
