#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable

try:
    import pyinotify
except ImportError:
    print("[Collector] pyinotify не установлен. Установите: pip install pyinotify")
    raise


class InotifyCollector:
    """Сбор файловых событий через inotify (без systemd)"""

    def __init__(self, watch_paths: List[str], callback: Optional[Callable] = None):
        self.watch_paths = [str(Path(p).resolve()) for p in watch_paths]
        self.callback = callback
        self.running = False
        self.wm = None
        self.notifier = None
        self._pending_move: Optional[Dict] = None

        self.event_map = {
            pyinotify.IN_OPEN: 'read',
            pyinotify.IN_MODIFY: 'write',
            pyinotify.IN_CLOSE_WRITE: 'write',
            pyinotify.IN_DELETE: 'delete',
            pyinotify.IN_DELETE_SELF: 'delete',
            pyinotify.IN_MOVED_FROM: 'move',
            pyinotify.IN_MOVED_TO: 'move',
            pyinotify.IN_CREATE: 'write',
        }

    def start(self):
        if not self.watch_paths:
            print("[Collector] Нет путей для мониторинга")
            return

        for path in self.watch_paths:
            if not os.path.exists(path):
                print(f"[Collector] Путь не существует: {path}")
                return

        print(f"[Collector] Запуск мониторинга: {self.watch_paths}")

        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(self.wm, self._event_handler, timeout=10)

        mask = (
            pyinotify.IN_OPEN |
            pyinotify.IN_MODIFY |
            pyinotify.IN_CLOSE_WRITE |
            pyinotify.IN_DELETE |
            pyinotify.IN_DELETE_SELF |
            pyinotify.IN_MOVED_FROM |
            pyinotify.IN_MOVED_TO |
            pyinotify.IN_CREATE
        )

        for path in self.watch_paths:
            self.wm.add_watch(path, mask, rec=True, auto_add=True)
            print(f"[Collector]   Мониторинг: {path}")

        self.running = True
        try:
            while self.running:
                self.notifier.process_events()
                if self.notifier.check_events():
                    self.notifier.read_events()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"[Collector] Ошибка: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.notifier:
            self.notifier.stop()
        print("[Collector] Остановлен")

    def _event_handler(self, event: pyinotify.Event):
        if any(x in event.pathname for x in ['.git', '__pycache__', '.swp', '~']):
            return

        event_type = self._get_event_type(event)
        if not event_type:
            return

        user = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))

        audit_event = {
            'event_type': event_type,
            'user': user,
            'file_path': event.pathname,
            'old_path': None,
            'metadata': {
                'event_mask': event.maskname,
                'pid': event.pid
            },
            'created_at': datetime.utcnow().isoformat()
        }

        if event.mask & pyinotify.IN_MOVED_FROM:
            self._pending_move = {'pathname': event.pathname, 'cookie': event.cookie}
            return

        if event.mask & pyinotify.IN_MOVED_TO:
            if self._pending_move and self._pending_move.get('cookie') == event.cookie:
                audit_event['old_path'] = self._pending_move['pathname']
                self._pending_move = None

        if self.callback:
            self.callback(audit_event)

    def _get_event_type(self, event: pyinotify.Event) -> Optional[str]:
        for mask, etype in self.event_map.items():
            if event.mask & mask:
                return etype
        return None
