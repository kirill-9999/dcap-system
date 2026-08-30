# audit-agent-s3/src/state.py
import json
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)


class StateManager:
    """Управление состоянием агента (agent_id, last_processed).

    Каждое значение хранится в отдельном JSON-файле внутри state_dir.
    """

    def __init__(self, state_dir: str = "data/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения."""
        if key in self._cache:
            return self._cache[key]

        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    value = json.load(f)
                    self._cache[key] = value
                    return value
            except Exception as e:
                logger.warning(f"Error loading state {key}: {e}")

        return default

    def set(self, key: str, value: Any):
        """Сохранение значения."""
        state_file = self.state_dir / f"{key}.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(value, f, indent=2, default=str, ensure_ascii=False)
            self._cache[key] = value
            logger.debug(f"State saved: {key}={value}")
        except Exception as e:
            logger.error(f"Error saving state {key}: {e}")

    def delete(self, key: str):
        """Удаление состояния."""
        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            state_file.unlink()
        if key in self._cache:
            del self._cache[key]

    def get_agent_id(self):
        """Получение agent_id."""
        return self.get("agent_id")

    def set_agent_id(self, agent_id):
        """Сохранение agent_id."""
        self.set("agent_id", agent_id)

    def get_last_processed(self):
        """Получение последнего обработанного файла."""
        return self.get("last_processed")

    def set_last_processed(self, key: str):
        """Сохранение последнего обработанного файла."""
        self.set("last_processed", key)
