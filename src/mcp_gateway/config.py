"""Конфигурация MCP-Gateway через pydantic-settings."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Конфигурация MCP-Gateway.

    Загружается из переменных окружения и ~/.env.
    Все параметры валидируются при старте.

    Attributes:
        gateway_host: IP-адрес для прослушивания.
        gateway_port: Порт MCP-сервера.
        gateway_log_level: Уровень логирования.
        gateway_log_format: Формат логов (json/console).
        gateway_config_file: Путь к config.yml с настройками модулей.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gateway_host: str = Field("127.0.0.1", description="IP-адрес для прослушивания")
    gateway_port: int = Field(8200, description="Порт MCP-сервера")
    gateway_log_level: str = Field("INFO", description="Уровень логирования")
    gateway_log_format: str = Field("json", description="Формат логов: json или console")
    gateway_config_file: str = Field("config.yml", description="Путь к config.yml")


def load_module_config(config_file: str = "config.yml") -> dict[str, dict[str, object]]:
    """Загружает конфигурацию модулей из config.yml.

    Args:
        config_file: Путь к файлу конфигурации.

    Returns:
        Словарь {имя_модуля: {enabled: bool, ...}}.
    """
    path = Path(config_file)
    if not path.exists():
        return {}
    with path.open() as f:
        data: dict[str, object] = yaml.safe_load(f) or {}
    result = data.get("modules", {})
    return result if isinstance(result, dict) else {}
