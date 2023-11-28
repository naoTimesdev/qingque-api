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

from blacksheep import Application
from rodi import Container

from app.docs import configure_docs
from app.errors import configure_error_handlers
from app.services import configure_services
from app.settings import Settings, load_settings
from domain.starrail.caching import StarRailImageCache
from domain.starrail.loader import SRSDataLoaderI18n
from domain.starrail.scoring import RelicScoring
from qutils.tooling import ROOT_DIR, get_logger, setup_logger

logger = get_logger("qingque.api.main")


def configure_application(
    services: Container,
    settings: Settings,
) -> Application:
    setup_logger(ROOT_DIR / "logs" / "app.log")

    app = Application(services=services, show_error_details=settings.app.show_error_details)

    configure_error_handlers(app)
    configure_docs(app, settings)
    return app


async def dispose_cache_and_everything(app: Application):
    logger.info("Disposing relic scores...")
    relic_scores = app.services.resolve(RelicScoring)
    relic_scores.unload()

    logger.info("Disposing cache...")
    srs_cache = app.services.resolve(StarRailImageCache)
    await srs_cache.clear()

    logger.info("Disposing SRS i18n")
    srs_i18n = app.services.resolve(SRSDataLoaderI18n)
    srs_i18n.clear()


app = configure_application(*configure_services(load_settings()))
app.on_stop += dispose_cache_and_everything
