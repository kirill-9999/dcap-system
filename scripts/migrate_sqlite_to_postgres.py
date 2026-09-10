#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Миграция данных из SQLite в PostgreSQL (День 36-37).

Переносит ВСЕ таблицы Manager, включая архивные (audit_logs_archive,
findings_archive). Использование:

    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite manager/dcap.db \
        --postgres postgresql://dcap:dcap123@localhost:5432/dcap \
        [--reset] [--report]

Порядок переноса соответствует зависимостям (resources, scanners, ...),
FK-проверки на этапе загрузки отключены (SET session_replication_role=replica),
в конце включаются обратно. Партиции audit_logs на PostgreSQL создаются
через Alembic-миграцию 001_initial_postgres (выполните alembic upgrade head
до запуска этого скрипта).
"""
import argparse
import os
import sys
from datetime import datetime

# Корень репозитория (для manager.src.*) и manager/src (для верхнеуровневых)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "manager", "src"))


def _log(msg: str) -> None:
    print(f"[{datetime.utcnow().isoformat(timespec='seconds')}] {msg}", flush=True)


def _connect_sqlite(path: str):
    from sqlalchemy import create_engine

    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def _table_order():
    """Порядок таблиц для переноса: зависимости сначала."""
    return [
        "roles",
        "users",
        "user_roles",
        "resources",
        "scanners",
        "scan_tasks",
        "findings",
        "catalog_entries",
        "failed_files",
        "schedules",
        "access_entries",
        "permission_changes",
        "access_alerts",
        "audit_agents",
        "audit_logs",
        "audit_logs_archive",
        "findings_archive",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Перенос данных SQLite -> PostgreSQL")
    parser.add_argument("--sqlite", default="manager/dcap.db", help="Путь к SQLite (manager/dcap.db)")
    parser.add_argument("--postgres", default="postgresql://dcap:dcap123@localhost:5432/dcap",
                        help="PostgreSQL URL")
    parser.add_argument("--reset", action="store_true", help="Очистить целевые таблицы перед переносом")
    parser.add_argument("--report", action="store_true", help="Вывести статистику по таблицам")
    args = parser.parse_args()

    from sqlalchemy import text

    src = _connect_sqlite(args.sqlite)
    dst = __import__("sqlalchemy").create_engine(args.postgres)

    from manager.src.db import models  # noqa: F401  (импорт моделей, регистрация metadata)
    from manager.src.auth import models as auth_models  # noqa: F401, E402  (users/roles/user_roles)

    if args.reset:
        _log(f"RESET: очистка таблиц PostgreSQL")
        with dst.begin() as conn:
            conn.execute(text("SET session_replication_role = replica"))
            for table in reversed(_table_order()):
                conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')).close()
            conn.execute(text("SET session_replication_role = DEFAULT"))

    total_rows = 0
    report = {}
    _log("Начинаю перенос данных...")

    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import Boolean as sa_Boolean

    with dst.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            with src.connect() as sconn:
                for table_name in _table_order():
                    meta = None
                    for table in models.Base.metadata.sorted_tables:
                        if table.name == table_name:
                            meta = table
                            break
                    if meta is None:
                        _log(f"  [SKIP] {table_name}: не найдена в metadata")
                        continue

                    # Проверяем существование таблицы в обоих концах
                    src_insp = sa_inspect(sconn)
                    if not src_insp.has_table(table_name):
                        _log(f"  [SKIP] {table_name}: отсутствует в SQLite")
                        continue

                    try:
                        rows = sconn.execute(text(f'SELECT * FROM "{table_name}"')).fetchall()
                    except Exception as e:  # noqa: BLE001
                        _log(f"  [ERROR] {table_name}: чтение из SQLite: {e}")
                        continue

                    if not rows:
                        _log(f"  {table_name}: пусто (0 строк)")
                        report[table_name] = 0
                        continue

                    dst_insp = sa_inspect(conn)
                    if not dst_insp.has_table(table_name):
                        _log(f"  [SKIP] {table_name}: отсутствует в PostgreSQL (запустите alembic upgrade head)")
                        report[table_name] = "SKIP (нет таблицы)"
                        continue

                    columns = [c.name for c in meta.columns.values()]
                    # Имена колонок через double-quote
                    col_names = ",".join(f'"{c}"' for c in columns)
                    placeholders = ",".join(f":{c}" for c in columns)

                    data = [dict(zip(columns, row)) for row in rows]
                    # Нормализация типов: datetime -> ISO str, bool (SQLite int) -> bool
                    type_map = {c.name: c.type for c in meta.columns.values()}
                    for item in data:
                        for k, v in item.items():
                            if v is None:
                                continue
                            if isinstance(v, (datetime,)):
                                item[k] = v.isoformat() if v.tzinfo is None else v.astimezone().isoformat()
                            elif isinstance(v, (int, float)) and isinstance(type_map.get(k), (sa_Boolean,)):
                                item[k] = bool(v)

                    conn.execute(
                        text(f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'),
                        data,
                    )
                    _log(f"  {table_name}: {len(data)} строк")
                    report[table_name] = len(data)
                    total_rows += len(data)
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))

    _log(f"Перенос завершён: всего {total_rows} строк")
    if args.report:
        print("\n=== Отчёт ===")
        for k, v in report.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())