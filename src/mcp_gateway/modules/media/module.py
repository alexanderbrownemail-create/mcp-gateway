"""Модуль media — конвертация и обработка медиафайлов."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_gateway.modules.base import BaseModule

logger = structlog.get_logger(__name__)


class MediaModule(BaseModule):
    """Модуль обработки медиафайлов.

    Предоставляет инструменты конвертации: текст → аудио (TTS),
    изображения → PDF, видео-информацию.

    Attributes:
        name: Уникальное имя модуля.
    """

    name = "media"

    async def startup(self) -> None:
        """Нет инициализации."""
        logger.info("media_module_ready")

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует media_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """

        @mcp.tool()
        async def media_tts(
            text: str,
            output_path: str,
            voice: str = "ru-RU-SvetlanaNeural",
            format: str = "ogg",
        ) -> dict[str, object]:
            """Синтезировать речь и сохранить аудиофайл.

            Использует edge-tts для синтеза. Для отправки в Telegram как голосовое —
            используй format='ogg' (ogg-24khz-16bit-mono-opus).

            Args:
                text: Текст для синтеза (до 4096 символов).
                output_path: Абсолютный путь для сохранения файла.
                voice: Голос edge-tts (например, ru-RU-SvetlanaNeural, en-US-AriaNeural).
                format: Формат аудио: 'ogg' (для Telegram voice) или 'mp3'.

            Returns:
                Словарь {ok, path, size_bytes}.
            """
            import edge_tts  # type: ignore[import-untyped]

            if len(text) > 4096:
                return {"ok": False, "error": "Text too long (max 4096 chars)"}

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            try:
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(output))
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            logger.info("media_tts", path=str(output), voice=voice)
            return {"ok": True, "path": str(output.resolve()), "size_bytes": output.stat().st_size}

        @mcp.tool()
        async def media_image_info(
            file_path: str,
        ) -> dict[str, object]:
            """Получить метаданные изображения.

            Args:
                file_path: Абсолютный путь к изображению (PNG, JPEG, WebP и др.).

            Returns:
                Словарь {ok, format, width, height, size_bytes, mode}.
            """
            try:
                from PIL import Image  # type: ignore[import-untyped]

                with Image.open(file_path) as img:
                    return {
                        "ok": True,
                        "format": img.format,
                        "width": img.width,
                        "height": img.height,
                        "mode": img.mode,
                        "size_bytes": Path(file_path).stat().st_size,
                    }
            except ImportError:
                return {"ok": False, "error": "Pillow not installed (pip install Pillow)"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def media_convert_image(
            input_path: str,
            output_path: str,
            width: int | None = None,
            height: int | None = None,
            quality: int = 85,
        ) -> dict[str, object]:
            """Конвертировать и/или изменить размер изображения.

            Args:
                input_path: Абсолютный путь к исходному изображению.
                output_path: Абсолютный путь для сохранения результата.
                width: Новая ширина (опционально; если задана только одна сторона — пропорционально).
                height: Новая высота (опционально).
                quality: Качество для JPEG/WebP (1–95, по умолчанию 85).

            Returns:
                Словарь {ok, path, width, height, size_bytes}.
            """
            try:
                from PIL import Image  # type: ignore[import-untyped]

                with Image.open(input_path) as img:
                    if width or height:
                        orig_w, orig_h = img.size
                        if width and not height:
                            height = int(orig_h * width / orig_w)
                        elif height and not width:
                            width = int(orig_w * height / orig_h)
                        img = img.resize((width, height), Image.LANCZOS)  # type: ignore[arg-type]

                    out = Path(output_path)
                    out.parent.mkdir(parents=True, exist_ok=True)

                    save_kwargs: dict[str, object] = {}
                    if out.suffix.lower() in (".jpg", ".jpeg", ".webp"):
                        save_kwargs["quality"] = quality

                    img.save(str(out), **save_kwargs)
                    w, h = img.size

            except ImportError:
                return {"ok": False, "error": "Pillow not installed (pip install Pillow)"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return {
                "ok": True,
                "path": str(Path(output_path).resolve()),
                "width": w,
                "height": h,
                "size_bytes": Path(output_path).stat().st_size,
            }

    async def shutdown(self) -> None:
        """Нет активных ресурсов."""
