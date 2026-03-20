"""Pydantic-модели для модуля core."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- Входные модели ----------

class BashRequest(BaseModel):
    """Запрос на выполнение shell-команды.

    Attributes:
        command: Shell-команда для выполнения.
        timeout_ms: Таймаут в миллисекундах (по умолчанию 120 000).
        working_dir: Рабочая директория (опционально).
    """

    command: str = Field(..., min_length=1)
    timeout_ms: int = Field(120_000, ge=1, le=600_000)
    working_dir: str | None = None


class ReadRequest(BaseModel):
    """Запрос на чтение файла.

    Attributes:
        file_path: Абсолютный путь к файлу.
        offset: Номер строки, с которой начать чтение (1-based).
        limit: Максимальное количество строк.
    """

    file_path: str
    offset: int | None = Field(None, ge=1)
    limit: int | None = Field(None, ge=1)


class WriteRequest(BaseModel):
    """Запрос на создание/перезапись файла.

    Attributes:
        file_path: Абсолютный путь к файлу.
        content: Содержимое файла.
    """

    file_path: str
    content: str


class EditRequest(BaseModel):
    """Запрос на замену строки в файле (exact-string replacement).

    Attributes:
        file_path: Абсолютный путь к файлу.
        old_string: Искомая строка (должна быть уникальна в файле).
        new_string: Замена.
        replace_all: Заменить все вхождения (по умолчанию False).
    """

    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class GlobRequest(BaseModel):
    """Запрос поиска файлов по паттерну.

    Attributes:
        pattern: Glob-паттерн (например, '**/*.py').
        path: Базовая директория (опционально).
    """

    pattern: str = Field(..., min_length=1)
    path: str | None = None


class GrepRequest(BaseModel):
    """Запрос поиска содержимого файлов (ripgrep).

    Attributes:
        pattern: Регулярное выражение для поиска.
        path: Файл или директория (опционально).
        glob: Фильтр файлов по маске (например, '*.py').
        case_insensitive: Регистронезависимый поиск.
        context: Строк контекста вокруг совпадения.
        output_mode: 'content' | 'files' | 'count'.
    """

    pattern: str = Field(..., min_length=1)
    path: str | None = None
    glob: str | None = None
    case_insensitive: bool = False
    context: int = Field(0, ge=0, le=20)
    output_mode: str = "content"


class LsRequest(BaseModel):
    """Запрос списка файлов директории.

    Attributes:
        path: Директория (по умолчанию — текущая рабочая).
        all_files: Показывать скрытые файлы.
    """

    path: str = "."
    all_files: bool = False


class WebFetchRequest(BaseModel):
    """Запрос получения содержимого URL.

    Attributes:
        url: URL для запроса.
        max_length: Максимальная длина возвращаемого текста.
    """

    url: str = Field(..., min_length=7)
    max_length: int = Field(50_000, ge=100, le=200_000)


class WebSearchRequest(BaseModel):
    """Запрос веб-поиска.

    Attributes:
        query: Поисковый запрос.
        num_results: Количество результатов (1–20).
    """

    query: str = Field(..., min_length=1)
    num_results: int = Field(5, ge=1, le=20)


# ---------- Выходные модели ----------

class BashResult(BaseModel):
    """Результат выполнения shell-команды.

    Attributes:
        stdout: Стандартный вывод.
        stderr: Поток ошибок.
        exit_code: Код возврата процесса.
        timed_out: True, если команда превысила таймаут.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class ReadResult(BaseModel):
    """Результат чтения файла.

    Attributes:
        content: Содержимое файла (с номерами строк).
        total_lines: Общее количество строк в файле.
        lines_returned: Количество возвращённых строк.
    """

    content: str
    total_lines: int
    lines_returned: int


class WriteResult(BaseModel):
    """Результат записи файла.

    Attributes:
        ok: Успех операции.
        file_path: Путь к записанному файлу.
        bytes_written: Количество записанных байт.
    """

    ok: bool
    file_path: str
    bytes_written: int


class EditResult(BaseModel):
    """Результат редактирования файла.

    Attributes:
        ok: Успех операции.
        replacements: Количество выполненных замен.
    """

    ok: bool
    replacements: int


class GlobResult(BaseModel):
    """Результат поиска файлов по паттерну.

    Attributes:
        files: Список найденных путей (отсортирован по дате изменения).
        count: Количество найденных файлов.
    """

    files: list[str]
    count: int


class GrepResult(BaseModel):
    """Результат поиска по содержимому файлов.

    Attributes:
        output: Форматированный вывод ripgrep.
        match_count: Количество совпадений (если output_mode='count').
    """

    output: str
    match_count: int | None = None


class LsResult(BaseModel):
    """Результат списка файлов.

    Attributes:
        entries: Записи директории с метаданными.
        path: Абсолютный путь директории.
    """

    entries: list[dict[str, object]]
    path: str


class WebFetchResult(BaseModel):
    """Результат получения URL.

    Attributes:
        url: Запрошенный URL.
        text: Извлечённый текст страницы.
        status_code: HTTP-статус.
        truncated: True, если текст обрезан по max_length.
    """

    url: str
    text: str
    status_code: int
    truncated: bool = False


class WebSearchResult(BaseModel):
    """Результат веб-поиска.

    Attributes:
        query: Поисковый запрос.
        results: Список найденных результатов.
    """

    query: str
    results: list[dict[str, str]]
