"""Модуль tasks — замена сломанных TodoWrite/TodoRead в режиме --print."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule

logger = structlog.get_logger(__name__)


class TaskStatus(str, Enum):
    """Статус задачи."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Приоритет задачи."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Task(BaseModel):
    """Модель задачи.

    Attributes:
        id: Уникальный ID задачи.
        title: Краткое название.
        description: Подробное описание (опционально).
        status: Статус.
        priority: Приоритет.
        created_at: Время создания (ISO).
        updated_at: Время последнего обновления (ISO).
    """

    id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: str
    updated_at: str


class TasksSettings(BaseSettings):
    """Конфигурация tasks модуля.

    Attributes:
        tasks_file: Путь к JSON-файлу хранилища задач.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tasks_file: str = Field(
        "~/.mcp-gateway/tasks.json",
        description="Путь к JSON-файлу хранилища задач",
    )


class TasksModule(BaseModule):
    """Модуль управления задачами.

    Персистентное хранилище задач в JSON-файле.
    Замена сломанных TodoWrite/TodoRead инструментов Claude Code в режиме --print.

    Attributes:
        name: Уникальное имя модуля.
        _settings: Настройки модуля.
        _tasks_file: Путь к файлу задач.
        _tasks: Словарь задач {id: Task}.
    """

    name = "tasks"

    def __init__(self) -> None:
        self._settings = TasksSettings()
        self._tasks_file: Path | None = None
        self._tasks: dict[str, Task] = {}

    async def startup(self) -> None:
        """Загружает задачи из файла."""
        self._tasks_file = Path(self._settings.tasks_file).expanduser()
        self._tasks_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("tasks_module_ready", tasks_file=str(self._tasks_file), count=len(self._tasks))

    def _load(self) -> None:
        """Загружает задачи из JSON-файла."""
        assert self._tasks_file is not None
        if not self._tasks_file.exists():
            return
        try:
            data = json.loads(self._tasks_file.read_text(encoding="utf-8"))
            self._tasks = {t["id"]: Task(**t) for t in data}
        except Exception as exc:
            logger.warning("tasks_load_error", error=str(exc))

    def _save(self) -> None:
        """Сохраняет задачи в JSON-файл."""
        assert self._tasks_file is not None
        data = [t.model_dump() for t in self._tasks.values()]
        self._tasks_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует task_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """

        @mcp.tool()
        async def task_create(
            title: str,
            description: str | None = None,
            priority: str = "medium",
        ) -> dict[str, object]:
            """Создать новую задачу.

            Args:
                title: Краткое название задачи (до 200 символов).
                description: Подробное описание (опционально).
                priority: Приоритет: 'high', 'medium' (по умолчанию) или 'low'.

            Returns:
                Словарь {ok, task} с созданной задачей.
            """
            try:
                prio = TaskPriority(priority)
            except ValueError:
                return {"ok": False, "error": f"Invalid priority: {priority!r}. Use: high, medium, low"}

            now = datetime.now(timezone.utc).isoformat()
            task = Task(
                id=str(uuid.uuid4())[:8],
                title=title,
                description=description,
                priority=prio,
                created_at=now,
                updated_at=now,
            )
            self._tasks[task.id] = task
            self._save()
            logger.info("task_create", task_id=task.id, title=task.title)
            return {"ok": True, "task": task.model_dump()}

        @mcp.tool()
        async def task_update(
            task_id: str,
            status: str | None = None,
            title: str | None = None,
            description: str | None = None,
            priority: str | None = None,
        ) -> dict[str, object]:
            """Обновить задачу.

            Args:
                task_id: ID задачи (из task_create или task_list).
                status: Новый статус: 'pending', 'in_progress', 'completed', 'cancelled'.
                title: Новое название (опционально).
                description: Новое описание (опционально).
                priority: Новый приоритет: 'high', 'medium', 'low' (опционально).

            Returns:
                Словарь {ok, task} с обновлённой задачей.
            """
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task {task_id!r} not found"}

            if status is not None:
                try:
                    task.status = TaskStatus(status)
                except ValueError:
                    return {"ok": False, "error": f"Invalid status: {status!r}"}
            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if priority is not None:
                try:
                    task.priority = TaskPriority(priority)
                except ValueError:
                    return {"ok": False, "error": f"Invalid priority: {priority!r}"}

            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()
            logger.info("task_update", task_id=task_id, status=task.status)
            return {"ok": True, "task": task.model_dump()}

        @mcp.tool()
        async def task_list(
            status: str | None = None,
            priority: str | None = None,
        ) -> dict[str, object]:
            """Список задач с фильтрацией.

            Args:
                status: Фильтр по статусу: 'pending', 'in_progress', 'completed', 'cancelled'.
                priority: Фильтр по приоритету: 'high', 'medium', 'low'.

            Returns:
                Словарь {tasks: [...], count: int}.
            """
            tasks = list(self._tasks.values())

            if status:
                try:
                    st = TaskStatus(status)
                    tasks = [t for t in tasks if t.status == st]
                except ValueError:
                    return {"ok": False, "error": f"Invalid status: {status!r}"}

            if priority:
                try:
                    pr = TaskPriority(priority)
                    tasks = [t for t in tasks if t.priority == pr]
                except ValueError:
                    return {"ok": False, "error": f"Invalid priority: {priority!r}"}

            # Сортировка: приоритет desc, дата создания asc
            priority_order = {TaskPriority.HIGH: 0, TaskPriority.MEDIUM: 1, TaskPriority.LOW: 2}
            tasks.sort(key=lambda t: (priority_order[t.priority], t.created_at))

            return {"tasks": [t.model_dump() for t in tasks], "count": len(tasks)}

        @mcp.tool()
        async def task_delete(
            task_id: str,
        ) -> dict[str, object]:
            """Удалить задачу.

            Args:
                task_id: ID задачи.

            Returns:
                Словарь {ok}.
            """
            if task_id not in self._tasks:
                return {"ok": False, "error": f"Task {task_id!r} not found"}

            del self._tasks[task_id]
            self._save()
            logger.info("task_delete", task_id=task_id)
            return {"ok": True}

    async def shutdown(self) -> None:
        """Сохраняет задачи перед остановкой."""
        self._save()
