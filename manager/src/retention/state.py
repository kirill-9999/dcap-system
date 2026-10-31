# manager/src/retention/state.py
import json
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()
_state: dict = {
    "last_run": None,
    "last_result": None,
    "running": False,
}

_STATE_FILE_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "data" / "retention_state.json",  # manager/data
    Path("data/retention_state.json"),
]


def _state_file() -> Path:
    p = _STATE_FILE_CANDIDATES[0]
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except OSError:
        p = _STATE_FILE_CANDIDATES[1]
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def _load():
    global _state
    f = _state_file()
    try:
        if f.exists():
            with open(f, "r", encoding="utf-8") as fh:
                _state = json.load(fh)
    except (OSError, ValueError):
        _state = {"last_run": None, "last_result": None, "running": False}


def _save():
    with _lock:
        try:
            with open(_state_file(), "w", encoding="utf-8") as f:
                json.dump(_state, f, indent=2, default=str)
        except OSError:
            pass


def set_running(running: bool):
    with _lock:
        _state["running"] = running


def set_last_run(result: dict):
    with _lock:
        _state["running"] = False
        _state["last_run"] = datetime.utcnow().isoformat()
        _state["last_result"] = result
    _save()


def get_retention_status() -> dict:
    with _lock:
        if not _state.get("last_run"):
            _load()
        return dict(_state)


if not _state.get("last_run"):
    _load()

with _lock:
    if _state.get("running"):
        # Свежий процесс не может быть «выполняющимся» — сбрасываем устаревший флаг
        # (напр. после жёсткого прерывания прошлого процесса во время прогона).
        _state["running"] = False
