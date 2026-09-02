#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import time
from datetime import datetime
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
        "read": "read",
        "modified": "write",
        "created": "write",
        "deleted": "delete",
        "moved": "move",
    }

    SKIP_PATTERNS = [".git", "__pycache__", ".swp", "~", "agent.pid"]

    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback

    def _emit(self, event_type: str, src_path: str, dest_path: str = None):
        if any(x in src_path for x in self.SKIP_PATTERNS):
            return

        import getpass
        import platform

        user = getpass.getuser()

        audit_event = {
            "event_type": event_type,
            "event_source": "linux_agent",
            "user": user,
            "file_path": src_path,
            "old_path": dest_path,
            "source_host": platform.node(),
            "metadata": {"src": src_path},
            "created_at": datetime.now().isoformat(),
        }
        self.callback(audit_event)

    def on_read(self, event):
        self._emit("read", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._emit("write", event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._emit("write", event.src_path)

    def on_deleted(self, event):
        self._emit("delete", event.src_path)

    def on_moved(self, event):
        self._emit("move", event.src_path, event.dest_path)


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

    # ------------------------------------------------------------------
    # Сбор POSIX прав (День 33)
    # ------------------------------------------------------------------
    def collect_permissions(self, path: str) -> List[Dict]:
        """Сбор POSIX/ACL прав через getfacl (fallback — stat)."""
        if not os.path.exists(path):
            return []

        entries = self._collect_getfacl(path)
        if not entries:
            entries = self._collect_stat(path)
        return entries

    def _collect_getfacl(self, path: str) -> List[Dict]:
        """Сбор прав через getfacl — вывод в CSV-формате."""
        try:
            result = subprocess.run(
                ["getfacl", "-cp", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []

        entries = []
        owner = None
        group = None
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("# owner:"):
                owner = line.split(":", 1)[1].strip()
            elif line.startswith("# group:"):
                group = line.split(":", 1)[1].strip()
            elif line.startswith("user:") or line.startswith("group:"):
                parts = line.split(":")
                if len(parts) >= 3:
                    ptype = "user" if parts[0] == "user" else "group"
                    name = parts[1].strip()
                    perms = self._acl_to_perms(parts[2].strip())
                    entries.append(
                        {
                            "resource_path": path,
                            "principal_type": ptype,
                            "principal_name": name,
                            "permissions": perms,
                            "permission_source": "direct",
                            "is_inherited": False,
                        }
                    )
        # Владелец и группа файла
        if owner:
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "user",
                    "principal_name": owner,
                    "permissions": ["read", "write", "execute"],
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        if group:
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "group",
                    "principal_name": group,
                    "permissions": ["read", "execute"],
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        return entries

    @staticmethod
    def _acl_to_perms(rwx: str) -> List[str]:
        perms = []
        rwx = rwx.replace("-", "")
        if "r" in rwx:
            perms.append("read")
        if "w" in rwx:
            perms.append("write")
        if "x" in rwx:
            perms.append("execute")
        if not perms:
            perms.append("read")
        return perms

    def _collect_stat(self, path: str) -> List[Dict]:
        """Fallback — сбор основных прав через os.stat (без ACL)."""
        try:
            import pwd
            import grp

            st = os.stat(path)
            uid = st.st_uid
            gid = st.st_gid
            mode = st.st_mode
            owner = pwd.getpwuid(uid).pw_name
            group = grp.getgrgid(gid).gr_name
        except Exception:
            return []
        entries = []
        if mode & 0o400:
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "user",
                    "principal_name": owner,
                    "permissions": ["read"],
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        if mode & 0o200:
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "user",
                    "principal_name": owner,
                    "permissions": ["write"],
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        if mode & 0o040:
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "group",
                    "principal_name": group,
                    "permissions": ["read"],
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        return entries
