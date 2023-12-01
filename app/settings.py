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

from blacksheep.server.env import get_env, is_development
from config.common import Configuration, ConfigurationBuilder
from config.env import EnvVars
from config.toml import TOMLFile
from config.user import UserSettings
from msgspec import Struct, field


class APIInfo(Struct):
    title: str = field(default="Qingque API")
    version: str = field(default="0.1.0")


class HoyolabSettings(Struct):
    ltuid: int
    ltoken: str


class RedisSettings(Struct):
    host: str
    port: int
    password: str | None = field(default=None)


class App(Struct):
    show_error_details: bool
    # Set token transaction ttl to 3 days
    transaction_ttl: int = field(default=60 * 60 * 24 * 3)
    # Cache mihomo data for 5 minutes
    mihomo_ttl: int = field(default=60 * 5)
    # Cache for image, 3 minutes
    image_ttl: int = field(default=60 * 15)


class Settings(Struct):
    app: App
    info: APIInfo
    hoyolab: HoyolabSettings
    redis: RedisSettings
    env: str

    @classmethod
    def make(cls, **kwargs) -> Settings:
        # Check nested settings
        app = kwargs.get("app", {})
        hoyolab = kwargs.get("hoyolab", {})
        redis = kwargs.get("redis", {})
        info = kwargs.get("info", {})
        return cls(
            app=App(**app),
            hoyolab=HoyolabSettings(**hoyolab),
            redis=RedisSettings(**redis),
            info=APIInfo(**info),
            env=kwargs.get("env", "production"),
        )


def default_configuration_builder() -> ConfigurationBuilder:
    app_env = get_env()
    builder = ConfigurationBuilder(
        TOMLFile("settings.toml"),
        TOMLFile(f"settings.{app_env.lower()}.toml", optional=True),
        EnvVars("APP_"),
    )

    if is_development():
        # for development environment, settings stored in the user folder
        builder.add_source(UserSettings())

    return builder


def default_configuration() -> Configuration:
    builder = default_configuration_builder()
    return builder.build()


def load_settings() -> Settings:
    config_root = default_configuration()
    return config_root.bind(Settings.make)  # type: ignore
