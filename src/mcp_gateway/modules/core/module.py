"""Модуль core — реимплементация Claude Code native tools для OpenClaw mini-bot."""
from __future__ import annotations

import asyncio
import glob as _glob
import os
import stat
from datetime import datetime
from pathlib import Path

import httpx
import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule
from mcp_gateway.modules.core.models import (
    BashRequest,
    BashResult,
    EditRequest,
    EditResult,
    GlobRequest,
    GlobResult,
    GrepRequest,
    GrepResult,
    LsRequest,
    LsResult,
    ReadRequest,
    ReadResult,
    WebFetchRequest,
    WebFetchResult,
    WebSearchRequest,
    WebSearchResult,
    WriteRequest,
    WriteResult,
)

logger = structlog.get_logger(__name__)


class CoreSettings(BaseSettings):
    """Конфигурация core модуля.

    Attributes:
        brave_api_key: API-ключ Brave Search (опционально, для web_search).
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    brave_api_key: str | None = Field(None, description="Brave Search API key")


class CoreModule(BaseModule):
    """Модуль core — файловые операции, bash, веб.

    Предоставляет OpenClaw mini-bot инструменты файловой системы и исполнения команд,
    аналогичные нативным инструментам Claude Code (Read, Write, Edit, Bash, Glob, Grep).

    Attributes:
        name: Уникальное имя модуля.
        _settings: Настройки модуля.
        _http: HTTP-клиент для web_fetch / web_search.
    """

    name = "core"

    def __init__(self) -> None:
        self._settings = CoreSettings()
        self._http: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Инициализирует HTTP-клиент."""
        self._http = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "mcp-gateway/0.1 (core module)"},
        )
        logger.info("core_module_ready")

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует core_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """
        settings = self._settings

        @mcp.tool()
        async def core_bash(
            command: str,
            timeout_ms: int = 120_000,
            working_dir: str | None = None,
        ) -> dict[str, object]:
            """Выполнить shell-команду на сервере.

            Args:
                command: Команда для выполнения в bash.
                timeout_ms: Таймаут в миллисекундах (1–600 000, по умолчанию 120 000).
                working_dir: Рабочая директория (по умолчанию — домашняя).

            Returns:
                Словарь {stdout, stderr, exit_code, timed_out}.
            """
            req = BashRequest(command=command, timeout_ms=timeout_ms, working_dir=working_dir)
            cwd = req.working_dir or str(Path.home())
            timeout_sec = req.timeout_ms / 1000

            timed_out = False
            try:
                proc = await asyncio.create_subprocess_shell(
                    req.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
                try:
                    stdout_b, stderr_b = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout_sec
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    stdout_b, stderr_b = await proc.communicate()
                    timed_out = True

                result = BashResult(
                    stdout=stdout_b.decode(errors="replace"),
                    stderr=stderr_b.decode(errors="replace"),
                    exit_code=proc.returncode or 0,
                    timed_out=timed_out,
                )
            except Exception as exc:
                result = BashResult(
                    stdout="",
                    stderr=str(exc),
                    exit_code=1,
                )

            logger.info("core_bash", command=req.command[:80], exit_code=result.exit_code)
            return result.model_dump()

        @mcp.tool()
        async def core_read(
            file_path: str,
            offset: int | None = None,
            limit: int | None = None,
        ) -> dict[str, object]:
            """Прочитать файл (с поддержкой offset/limit).

            Args:
                file_path: Абсолютный путь к файлу.
                offset: Начальная строка (1-based, опционально).
                limit: Максимум строк (опционально).

            Returns:
                Словарь {content, total_lines, lines_returned}.
                content — строки с номерами в формате 'N→текст'.
            """
            req = ReadRequest(file_path=file_path, offset=offset, limit=limit)
            try:
                text = Path(req.file_path).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            all_lines = text.splitlines()
            total = len(all_lines)

            start = (req.offset - 1) if req.offset else 0
            end = (start + req.limit) if req.limit else total
            selected = all_lines[start:end]

            numbered = "\n".join(
                f"{start + i + 1}\t{line}" for i, line in enumerate(selected)
            )
            result = ReadResult(
                content=numbered,
                total_lines=total,
                lines_returned=len(selected),
            )
            return result.model_dump()

        @mcp.tool()
        async def core_write(
            file_path: str,
            content: str,
        ) -> dict[str, object]:
            """Создать или перезаписать файл.

            Args:
                file_path: Абсолютный путь к файлу.
                content: Содержимое файла.

            Returns:
                Словарь {ok, file_path, bytes_written}.
            """
            req = WriteRequest(file_path=file_path, content=content)
            try:
                p = Path(req.file_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                encoded = req.content.encode("utf-8")
                p.write_bytes(encoded)
                result = WriteResult(
                    ok=True,
                    file_path=str(p.resolve()),
                    bytes_written=len(encoded),
                )
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            logger.info("core_write", file_path=result.file_path, bytes=result.bytes_written)
            return result.model_dump()

        @mcp.tool()
        async def core_edit(
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,
        ) -> dict[str, object]:
            """Заменить строку в файле (exact-string replacement).

            Замена провалится, если old_string не найдена или (при replace_all=False)
            найдена более одного раза.

            Args:
                file_path: Абсолютный путь к файлу.
                old_string: Искомая строка (должна быть уникальна при replace_all=False).
                new_string: Строка-замена.
                replace_all: Заменить все вхождения (по умолчанию False).

            Returns:
                Словарь {ok, replacements}.
            """
            req = EditRequest(
                file_path=file_path,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
            )
            try:
                text = Path(req.file_path).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            count = text.count(req.old_string)
            if count == 0:
                return {"ok": False, "error": "old_string not found in file"}
            if not req.replace_all and count > 1:
                return {
                    "ok": False,
                    "error": f"old_string found {count} times; use replace_all=True or provide more context",
                }

            if req.replace_all:
                new_text = text.replace(req.old_string, req.new_string)
                replacements = count
            else:
                new_text = text.replace(req.old_string, req.new_string, 1)
                replacements = 1

            try:
                Path(req.file_path).write_text(new_text, encoding="utf-8")
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            result = EditResult(ok=True, replacements=replacements)
            logger.info("core_edit", file_path=req.file_path, replacements=replacements)
            return result.model_dump()

        @mcp.tool()
        async def core_glob(
            pattern: str,
            path: str | None = None,
        ) -> dict[str, object]:
            """Найти файлы по glob-паттерну.

            Args:
                pattern: Паттерн (например, '**/*.py', 'src/**/*.ts').
                path: Базовая директория (по умолчанию — CWD).

            Returns:
                Словарь {files, count}.
                files отсортированы по дате изменения (новейшие первые).
            """
            req = GlobRequest(pattern=pattern, path=path)
            base = Path(req.path) if req.path else Path.cwd()

            try:
                matches = list(base.glob(req.pattern))
                # Сортировка по дате изменения (новейшие первые)
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                files = [str(p) for p in matches if p.is_file()]
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            result = GlobResult(files=files, count=len(files))
            return result.model_dump()

        @mcp.tool()
        async def core_grep(
            pattern: str,
            path: str | None = None,
            glob: str | None = None,
            case_insensitive: bool = False,
            context: int = 0,
            output_mode: str = "content",
        ) -> dict[str, object]:
            """Поиск по содержимому файлов (ripgrep).

            Args:
                pattern: Регулярное выражение для поиска.
                path: Файл или директория (по умолчанию — CWD).
                glob: Фильтр файлов по маске (например, '*.py').
                case_insensitive: Регистронезависимый поиск.
                context: Строк контекста вокруг совпадения (0–20).
                output_mode: 'content' (по умолчанию), 'files' или 'count'.

            Returns:
                Словарь {output, match_count}.
            """
            req = GrepRequest(
                pattern=pattern,
                path=path,
                glob=glob,
                case_insensitive=case_insensitive,
                context=context,
                output_mode=output_mode,
            )

            cmd = ["rg", "--no-heading"]
            if req.case_insensitive:
                cmd.append("-i")
            if req.context > 0:
                cmd.extend(["-C", str(req.context)])
            if req.glob:
                cmd.extend(["--glob", req.glob])

            if req.output_mode == "files":
                cmd.append("-l")
            elif req.output_mode == "count":
                cmd.append("-c")

            cmd.append(req.pattern)
            if req.path:
                cmd.append(req.path)

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout_b.decode(errors="replace")
            except FileNotFoundError:
                # rg не установлен — fallback на Python grep
                output = _python_grep(req)
            except asyncio.TimeoutError:
                return {"ok": False, "error": "grep timed out"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            match_count: int | None = None
            if req.output_mode == "count":
                match_count = sum(
                    int(line.split(":")[-1])
                    for line in output.splitlines()
                    if ":" in line and line.split(":")[-1].isdigit()
                )

            result = GrepResult(output=output, match_count=match_count)
            return result.model_dump()

        @mcp.tool()
        async def core_ls(
            path: str = ".",
            all_files: bool = False,
        ) -> dict[str, object]:
            """Список файлов директории с метаданными.

            Args:
                path: Директория (по умолчанию — текущая рабочая).
                all_files: Показывать скрытые файлы (начинающиеся с '.').

            Returns:
                Словарь {entries, path}.
                entries — список {name, type, size, modified}.
            """
            req = LsRequest(path=path, all_files=all_files)
            try:
                p = Path(req.path).resolve()
                entries = []
                for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
                    if not req.all_files and item.name.startswith("."):
                        continue
                    s = item.stat()
                    entries.append({
                        "name": item.name,
                        "type": "file" if item.is_file() else "dir",
                        "size": s.st_size if item.is_file() else None,
                        "modified": datetime.fromtimestamp(s.st_mtime).isoformat(),
                    })
            except OSError as exc:
                return {"ok": False, "error": str(exc)}

            result = LsResult(entries=entries, path=str(p))
            return result.model_dump()

        @mcp.tool()
        async def core_web_fetch(
            url: str,
            max_length: int = 50_000,
        ) -> dict[str, object]:
            """Получить содержимое URL и вернуть как текст.

            HTML-страницы конвертируются в plain text (теги удаляются).

            Args:
                url: URL для запроса (http/https).
                max_length: Максимальная длина текста (100–200 000, по умолчанию 50 000).

            Returns:
                Словарь {url, text, status_code, truncated}.
            """
            assert self._http is not None
            req = WebFetchRequest(url=url, max_length=max_length)

            try:
                resp = await self._http.get(req.url)
                raw = resp.text
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                text = _strip_html(raw)
            else:
                text = raw

            truncated = len(text) > req.max_length
            result = WebFetchResult(
                url=str(resp.url),
                text=text[: req.max_length],
                status_code=resp.status_code,
                truncated=truncated,
            )
            return result.model_dump()

        @mcp.tool()
        async def core_web_search(
            query: str,
            num_results: int = 5,
        ) -> dict[str, object]:
            """Веб-поиск через Brave Search API.

            Требует переменной окружения BRAVE_API_KEY.

            Args:
                query: Поисковый запрос.
                num_results: Количество результатов (1–20, по умолчанию 5).

            Returns:
                Словарь {query, results} где results — [{title, url, description}].
            """
            assert self._http is not None
            req = WebSearchRequest(query=query, num_results=num_results)

            if not settings.brave_api_key:
                return {"ok": False, "error": "BRAVE_API_KEY not configured"}

            try:
                resp = await self._http.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": req.query, "count": req.num_results},
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": settings.brave_api_key,
                    },
                )
                resp.raise_for_status()
                data: dict[str, object] = resp.json()
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            web = data.get("web", {})
            assert isinstance(web, dict)
            items = web.get("results", [])
            assert isinstance(items, list)

            results = [
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "description": str(item.get("description", "")),
                }
                for item in items
            ]
            result = WebSearchResult(query=req.query, results=results)
            return result.model_dump()

    async def shutdown(self) -> None:
        """Закрывает HTTP-клиент."""
        if self._http:
            await self._http.aclose()


# ---------- Вспомогательные функции ----------

def _strip_html(html: str) -> str:
    """Удаляет HTML-теги и нормализует пробелы."""
    import re

    # Удалить script и style блоки
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Удалить все теги
    text = re.sub(r"<[^>]+>", " ", html)
    # Нормализовать пробелы
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _python_grep(req: GrepRequest) -> str:
    """Резервная реализация grep на Python (когда rg не установлен)."""
    import re

    flags = re.IGNORECASE if req.case_insensitive else 0
    try:
        pattern = re.compile(req.pattern, flags)
    except re.error as exc:
        return f"Invalid pattern: {exc}"

    base = Path(req.path) if req.path else Path.cwd()
    glob_pattern = req.glob or "*"
    lines_out: list[str] = []

    files: list[Path] = []
    if base.is_file():
        files = [base]
    else:
        files = list(base.rglob(glob_pattern))

    for filepath in sorted(files):
        if not filepath.is_file():
            continue
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                lines_out.append(f"{filepath}:{lineno}:{line}")

    return "\n".join(lines_out)
