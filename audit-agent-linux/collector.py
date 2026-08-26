#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Callable

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("[Collector] watchdog не установлен. Установите: pip install watchdog")
    raise


class _WatchdogHandler(FileSystemEventHandler):
    """Обработчик событий watchdog → audit_event"""

    EVENT_MAP = {
        'read': 'read',
        'modified': 'write',
        'created': 'write',
        'deleted': 'delete',
        'moved': 'move',
    }

    SKIP_PATTERNS = ['.git', '__pycache__', '.swp', '~', 'agent.pid']

    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback

    def _emit(self, event_type: str, src_path: str, dest_path: str = None):
        if any(x in src_path for x in self.SKIP_PATTERNS):
            return

        import getpass
        user = getpass.getuser()

        audit_event = {
            'event_type': event_type,
            'user': user,
            'file_path': src_path,
            'old_path': dest_path,
            'metadata': {'src': src_path},
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        self.callback(audit_event)

    def on_read(self, event):
        self._emit('read', event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._emit('write', event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._emit('write', event.src_path)

    def on_deleted(self, event):
        self._emit('delete', event.src_path)

    def on_moved(self, event):
        self._emit('move', event.src_path, event.dest_path)


class InotifyCollector:
    """Сбор файловых событий через inotify (watchdog)"""

    def __init__(self, watch_paths: List[str], callback: Optional[Callable] = None):
        self.watch_paths = [str(Path(p).resolve()) for p in watch_paths]
        self.callback = callback
        self.running = False
        self.observer = None

    def start(self):
        if not self.watch_paths:
            print("[Collector] Нет путей для мониторинга")
            return

        for path in self.watch_paths:
            if not os.path.exists(path):
                print(f"[Collector] Путь не существует: {path}")
                return

        print(f"[Collector] Запуск мониторинга: {self.watch_paths}")

        handler = _WatchdogHandler(callback=self.callback)
        self.observer = Observer()

        for path in self.watch_paths:
            self.observer.schedule(handler, path, recursive=True)
            print(f"[Collector]   Мониторинг: {path}")

        self.running = True
        self.observer.start()

        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"[Collector] Ошибка: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        print("[Collector] Остановлен")
