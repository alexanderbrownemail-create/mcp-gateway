"""Модуль memory — поиск и управление памятью агента."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule

logger = structlog.get_logger(__name__)


class MemorySettings(BaseSettings):
    """Конфигурация memory модуля.

    Attributes:
        memory_dir: Директория с markdown-файлами памяти.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    memory_dir: str = Field(
        "~/.openclaw/workspace/memory",
        description="Директория с файлами памяти агента (markdown)",
    )


class MemoryModule(BaseModule):
    """Модуль семантического поиска по памяти агента.

    Работает с markdown-файлами в директории памяти.
    Поиск — TF-IDF-подобный по ключевым словам (без внешних vector DB).

    Attributes:
        name: Уникальное имя модуля.
        _settings: Настройки модуля.
        _memory_dir: Путь к директории памяти.
    """

    name = "memory"

    def __init__(self) -> None:
        self._settings = MemorySettings()
        self._memory_dir: Path | None = None

    async def startup(self) -> None:
        """Инициализирует директорию памяти."""
        self._memory_dir = Path(self._settings.memory_dir).expanduser()
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        logger.info("memory_module_ready", memory_dir=str(self._memory_dir))

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует memory_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """

        @mcp.tool()
        async def memory_search(
            query: str,
            max_results: int = 10,
        ) -> dict[str, object]:
            """Семантический поиск по памяти агента.

            Ищет по всем markdown-файлам в директории памяти.
            Ранжирование — по количеству совпадений ключевых слов запроса.

            Args:
                query: Поисковый запрос (слова или фраза).
                max_results: Максимальное число результатов (1–50).

            Returns:
                Словарь {results: [{file, score, excerpt}], count: int}.
            """
            assert self._memory_dir is not None
            if max_results < 1 or max_results > 50:
                return {"ok": False, "error": "max_results must be 1–50"}

            keywords = set(re.findall(r"\w+", query.lower()))
            if not keywords:
                return {"ok": False, "error": "Empty query"}

            results = []
            for md_file in sorted(self._memory_dir.rglob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                text_lower = text.lower()
                score = sum(text_lower.count(kw) for kw in keywords)
                if score == 0:
                    continue

                # Найти первое вхождение любого ключевого слова для excerpt
                excerpt = _find_excerpt(text, keywords)
                results.append({
                    "file": str(md_file.relative_to(self._memory_dir)),
                    "score": score,
                    "excerpt": excerpt,
                })

            results.sort(key=lambda r: r["score"], reverse=True)
            results = results[:max_results]

            return {"results": results, "count": len(results)}

        @mcp.tool()
        async def memory_get(
            file: str,
        ) -> dict[str, object]:
            """Прочитать конкретный файл памяти.

            Args:
                file: Относительный путь файла внутри директории памяти
                      (например, 'user_preferences.md' или 'projects/openclaw.md').

            Returns:
                Словарь {file, content, size}.
            """
            assert self._memory_dir is not None
            path = (self._memory_dir / file).resolve()

            # Проверка path traversal
            if not str(path).startswith(str(self._memory_dir.resolve())):
                return {"ok": False, "error": "Access denied: path outside memory directory"}

            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                return {"ok": False, "error": f"File not found: {file}"}
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            return {"file": file, "content": content, "size": len(content)}

        @mcp.tool()
        async def memory_write(
            file: str,
            content: str,
        ) -> dict[str, object]:
            """Записать или обновить файл памяти.

            Args:
                file: Относительный путь файла (например, 'user_preferences.md').
                      Поддиректории создаются автоматически.
                content: Markdown-содержимое файла.

            Returns:
                Словарь {ok, file, bytes_written}.
            """
            assert self._memory_dir is not None
            path = (self._memory_dir / file).resolve()

            # Проверка path traversal
            if not str(path).startswith(str(self._memory_dir.resolve())):
                return {"ok": False, "error": "Access denied: path outside memory directory"}

            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                encoded = content.encode("utf-8")
                path.write_bytes(encoded)
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            logger.info("memory_write", file=file, size=len(encoded))
            return {"ok": True, "file": file, "bytes_written": len(encoded)}

    async def shutdown(self) -> None:
        """Нет активных ресурсов для освобождения."""


def _find_excerpt(text: str, keywords: set[str], context: int = 200) -> str:
    """Находит первое вхождение ключевого слова и возвращает контекст вокруг него."""
    text_lower = text.lower()
    best_pos = len(text)

    for kw in keywords:
        pos = text_lower.find(kw)
        if 0 <= pos < best_pos:
            best_pos = pos

    if best_pos == len(text):
        return text[:context].replace("\n", " ").strip()

    start = max(0, best_pos - context // 2)
    end = min(len(text), best_pos + context // 2)
    excerpt = text[start:end].replace("\n", " ").strip()

    if start > 0:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt = excerpt + "…"

    return excerpt
