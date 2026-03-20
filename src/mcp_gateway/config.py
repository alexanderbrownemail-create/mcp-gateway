"""MCP-Gateway application settings."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gateway_host: str = Field("127.0.0.1", description="MCP server bind host")
    gateway_port: int = Field(8200, description="MCP server bind port")
    gateway_log_level: str = Field("INFO", description="Logging level")
    gateway_config_file: str = Field("config.yml", description="Path to config.yml")


def load_module_config(config_file: str = "config.yml") -> dict:
    """Load module enable/disable config from config.yml."""
    path = Path(config_file)
    if not path.exists():
        return {}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("modules", {})
