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

from pathlib import Path

from rodi import Container

from app.settings import Settings
from domain.hylab.client import HYLabClient
from domain.i18n import QingqueI18n, QingqueLanguage
from domain.mihomo.client import MihomoAPI
from domain.redisdb import RedisDatabase
from domain.starrail.caching import StarRailImageCache
from domain.starrail.loader import SRSDataLoader, SRSDataLoaderI18n
from domain.starrail.scoring import RelicScoring
from domain.transcations import TransactionsHelper
from qutils.tooling import ROOT_DIR, get_logger

SRS_FOLDER = ROOT_DIR / "assets" / "srs"
SRS_EXTRAS = ROOT_DIR / "assets" / "images"
logger = get_logger("qingque.api.services")


def _preload_srs_assets() -> StarRailImageCache:
    srs_img_cache = StarRailImageCache()
    # Element
    elem_folder = Path(SRS_FOLDER / "icon" / "element")
    logger.debug(f"Preloading SRS assets: {elem_folder}...")

    for elem_icon in elem_folder.glob("*.png"):
        srs_img_cache.get_sync(elem_icon)

    SELECTED_DECO = [
        "DecoShortLineRing177R@3x.png",
        "DialogFrameDeco1.png",
        "DialogFrameDeco1@3x.png",
        "NewSystemDecoLine.png",
        "StarBig.png",
        "StarBig_WhiteGlow.png",
        "IconCompassDeco.png",
    ]
    logger.debug("Preloading SRS assets: pre-selected deco...")
    for deco in SELECTED_DECO:
        srs_img_cache.get_sync(Path(SRS_FOLDER / "icon" / "deco" / deco))
    srs_img_cache.get_sync(Path(SRS_EXTRAS / "MihomoCardDeco50.png"))
    srs_img_cache.get_sync(Path(SRS_EXTRAS / "PomPomDecoStamp.png"))

    # Path
    path_folder = Path(SRS_FOLDER / "icon" / "path")
    logger.debug(f"Preloading SRS assets: {path_folder}...")
    for path_icon in path_folder.glob("*.png"):
        srs_img_cache.get_sync(path_icon)

    # Property
    prop_folder = Path(SRS_FOLDER / "icon" / "property")
    logger.debug(f"Preloading SRS assets: {prop_folder}...")
    for prop_icon in prop_folder.glob("*.png"):
        srs_img_cache.get_sync(prop_icon)

    return srs_img_cache


def _load_srs_data() -> SRSDataLoaderI18n:
    data_loader = SRSDataLoaderI18n()
    for lang in list(QingqueLanguage):
        loader = SRSDataLoader(lang.to_mihomo())
        logger.debug(f"Loading SRS data for {lang}...")
        loader.loads()
        data_loader.set(lang, loader)
    return data_loader


def configure_services(settings: Settings) -> tuple[Container, Settings]:
    i18n_path = ROOT_DIR / "i18n"

    container = Container()

    logger.info("Configuring services...")
    i18n = QingqueI18n(i18n_path)
    mihomo = MihomoAPI()
    hylab = HYLabClient(settings.hoyolab.ltuid, settings.hoyolab.ltoken)
    logger.info("Connecting to Redis...")
    redis = RedisDatabase(settings.redis.host, settings.redis.port, settings.redis.password)
    transactions = TransactionsHelper(redis=redis)
    logger.info("Loading SRS assets...")
    srs_cache = _preload_srs_assets()
    srs_i18n = _load_srs_data()
    logger.info("Loading relic scores...")
    relic_scores = RelicScoring(Path(ROOT_DIR / "assets" / "relic_scores.json"))
    relic_scores.load()

    container.add_instance(settings)
    container.add_instance(i18n)
    container.add_instance(mihomo)
    container.add_instance(hylab)
    container.add_instance(redis)
    container.add_instance(transactions)
    container.add_instance(srs_cache)
    container.add_instance(srs_i18n)
    container.add_instance(relic_scores)

    return container, settings
