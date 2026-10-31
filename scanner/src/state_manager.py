"""Состояние сканирования задания — для resume после остановки.

День 53.4n (v3.14.12, BUG-280): при Ctrl+C / остановке сканера задание не
превращается в failed, а ставится обратно в очередь Manager (release).
Сканер запоминает, до какого чанка дошёл, и при повторном получении задания
продолжает с следующего чанка.

Файл состояния — один на задание: <state_dir>/scan_<task_id>.json.
Запись атомарная (временный файл в том же каталоге + os.replace), чтобы
убийство процесса не оставило полусохранённый JSON.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STATE_DIR = Path("scanner/state")

# Состояние старше 24 часов не используем: файлы могли измениться,
# а Manager уже вернул задание в pending по таймауту.
MAX_AGE_HOURS = 24


class ScanState:
    """Персистентное состояние сканирования одного задания."""

    def __init__(self, task_id: int, state_dir: Optional[str] = None):
        self.task_id = int(task_id)
        self.state_dir = Path(state_dir) if state_dir else STATE_DIR
        self.state_file = self.state_dir / f"scan_{self.task_id}.json"
        self.data: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """Загрузить состояние. Возвращает {} если нет/битое/чужое/старое."""
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[Resume] Не удалось прочитать %s: %s", self.state_file, exc)
            return {}

        try:
            saved_task_id = int(data.get("task_id", -1))
        except (TypeError, ValueError):
            saved_task_id = -1
        if saved_task_id != self.task_id:
            logger.warning(
                "[Resume] %s принадлежит другому заданию (%s) — игнорируем",
                self.state_file,
                saved_task_id,
            )
            return {}

        updated_at = data.get("updated_at")
        if updated_at:
            try:
                age_sec = (datetime.utcnow() - datetime.fromisoformat(updated_at)).total_seconds()
                if age_sec > MAX_AGE_HOURS * 3600:
                    logger.info(
                        "[Resume] Состояние задания %d устарело (%.1f ч) — начинаем с нуля",
                        self.task_id,
                        age_sec / 3600,
                    )
                    self.clear()
                    return {}
            except (TypeError, ValueError):
                pass

        self.data = data
        return data

    def save(self, **kwargs: Any) -> None:
        """Атомарно сохранить состояние (переданные поля мержатся)."""
        self.data.update(kwargs)
        self.data["task_id"] = self.task_id
        self.data["updated_at"] = datetime.utcnow().isoformat()

        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=f".scan_{self.task_id}.",
                suffix=".tmp",
                dir=str(self.state_dir),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.state_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.error("[Resume] Не удалось сохранить %s: %s", self.state_file, exc)

    def clear(self) -> None:
        """Удалить файл состояния (задание завершено или состояние невалидно)."""
        self.data = {}
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.debug("[Resume] Состояние %s удалено", self.state_file)
        except OSError as exc:
            logger.warning("[Resume] Не удалось удалить %s: %s", self.state_file, exc)

    def get_resume_chunk(self) -> int:
        """Индекс первого необработанного чанка (0 — начинать сначала)."""
        try:
            return max(0, int(self.data.get("last_completed_chunk", -1)) + 1)
        except (TypeError, ValueError):
            return 0

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
