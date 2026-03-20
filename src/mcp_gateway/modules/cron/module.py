"""Модуль cron — планировщик задач по расписанию."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_gateway.modules.base import BaseModule

logger = structlog.get_logger(__name__)


class CronJobStatus(str, Enum):
    """Статус cron-задачи."""

    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


class CronJob(BaseModel):
    """Cron-задача.

    Attributes:
        id: Уникальный ID задачи.
        expression: Cron-выражение (например, '*/5 * * * *').
        tool_name: Имя MCP-инструмента для вызова.
        tool_args: Аргументы инструмента (JSON-совместимый dict).
        status: Статус задачи.
        description: Описание задачи.
        created_at: Время создания (ISO).
        last_run: Время последнего запуска (ISO, если был).
        run_count: Количество запусков.
    """

    id: str
    expression: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    status: CronJobStatus = CronJobStatus.ACTIVE
    description: str = ""
    created_at: str
    last_run: str | None = None
    run_count: int = 0


class CronModule(BaseModule):
    """Модуль планировщика задач по расписанию.

    Позволяет создавать периодические задачи по cron-выражению.
    При срабатывании вызывает зарегистрированный MCP-инструмент.

    Attributes:
        name: Уникальное имя модуля.
        _jobs: Словарь {job_id: CronJob}.
        _task: Background asyncio task планировщика.
    """

    name = "cron"

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task[None] | None = None
        self._mcp: FastMCP | None = None

    async def startup(self) -> None:
        """Запускает фоновый планировщик."""
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("cron_module_ready")

    async def _scheduler_loop(self) -> None:
        """Главный цикл планировщика — проверяет расписание каждую минуту."""
        while True:
            try:
                await asyncio.sleep(60)
                now = datetime.now(timezone.utc)
                for job in list(self._jobs.values()):
                    if job.status != CronJobStatus.ACTIVE:
                        continue
                    if _cron_matches(job.expression, now):
                        await self._run_job(job, now)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("cron_scheduler_error", error=str(exc))

    async def _run_job(self, job: CronJob, now: datetime) -> None:
        """Выполняет cron-задачу."""
        logger.info("cron_job_run", job_id=job.id, tool=job.tool_name)
        job.last_run = now.isoformat()
        job.run_count += 1
        # Реальный вызов инструмента — через call_tool FastMCP (если доступно)
        if self._mcp is not None:
            try:
                await self._mcp.call_tool(job.tool_name, job.tool_args)  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning("cron_job_error", job_id=job.id, error=str(exc))

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует cron_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """
        self._mcp = mcp

        @mcp.tool()
        async def cron_create(
            expression: str,
            tool_name: str,
            tool_args: dict[str, object] | None = None,
            description: str = "",
        ) -> dict[str, object]:
            """Создать задачу по расписанию.

            Args:
                expression: Cron-выражение (5 полей: минуты часы день месяц день_недели).
                            Примеры: '*/5 * * * *' — каждые 5 минут,
                                     '0 9 * * 1-5' — рабочие дни в 9:00.
                tool_name: Имя MCP-инструмента для вызова (например, 'bot_send_message').
                tool_args: Аргументы инструмента (JSON-совместимый dict).
                description: Описание задачи (опционально).

            Returns:
                Словарь {ok, job} с созданной задачей.
            """
            now = datetime.now(timezone.utc).isoformat()
            job = CronJob(
                id=str(uuid.uuid4())[:8],
                expression=expression,
                tool_name=tool_name,
                tool_args=tool_args or {},
                description=description,
                created_at=now,
            )
            self._jobs[job.id] = job
            logger.info("cron_create", job_id=job.id, expression=expression, tool=tool_name)
            return {"ok": True, "job": job.model_dump()}

        @mcp.tool()
        async def cron_list() -> dict[str, object]:
            """Список всех cron-задач.

            Returns:
                Словарь {jobs: [...], count: int}.
            """
            jobs = [j.model_dump() for j in self._jobs.values()]
            return {"jobs": jobs, "count": len(jobs)}

        @mcp.tool()
        async def cron_pause(
            job_id: str,
        ) -> dict[str, object]:
            """Приостановить cron-задачу.

            Args:
                job_id: ID задачи.

            Returns:
                Словарь {ok, job_id, status}.
            """
            job = self._jobs.get(job_id)
            if not job:
                return {"ok": False, "error": f"Job {job_id!r} not found"}
            job.status = CronJobStatus.PAUSED
            logger.info("cron_pause", job_id=job_id)
            return {"ok": True, "job_id": job_id, "status": job.status}

        @mcp.tool()
        async def cron_delete(
            job_id: str,
        ) -> dict[str, object]:
            """Удалить cron-задачу.

            Args:
                job_id: ID задачи.

            Returns:
                Словарь {ok}.
            """
            if job_id not in self._jobs:
                return {"ok": False, "error": f"Job {job_id!r} not found"}
            del self._jobs[job_id]
            logger.info("cron_delete", job_id=job_id)
            return {"ok": True}

    async def shutdown(self) -> None:
        """Останавливает фоновый планировщик."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


def _cron_matches(expression: str, now: datetime) -> bool:
    """Проверяет, соответствует ли текущее время cron-выражению.

    Поддерживает стандартный формат 5 полей: мин час день мес д_нед.
    Поддерживает: '*', числа, диапазоны (1-5), шаги (*/5).
    """
    parts = expression.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, day, month, weekday = parts
    checks = [
        (minute, now.minute, 0, 59),
        (hour, now.hour, 0, 23),
        (day, now.day, 1, 31),
        (month, now.month, 1, 12),
        (weekday, now.weekday(), 0, 6),
    ]
    return all(_field_matches(field, value) for field, value, *_ in checks)


def _field_matches(field: str, value: int) -> bool:
    """Проверяет одно поле cron-выражения."""
    if field == "*":
        return True

    for part in field.split(","):
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if base == "*":
                if value % step == 0:
                    return True
            else:
                start = int(base)
                if value >= start and (value - start) % step == 0:
                    return True
        elif "-" in part:
            start, end = part.split("-", 1)
            if int(start) <= value <= int(end):
                return True
        else:
            if int(part) == value:
                return True

    return False
