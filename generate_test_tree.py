#!/usr/bin/env python3
"""
Генератор тестовых данных для папки: 100 подпапок × 10 уровней глубины.

В репозитории: E:\\projects\\dcap-system\\test_files\\test_scan_tree
"""
import os
import sys
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent / "test_files" / "test_scan_tree"

# Наборы содержимого для разных типов файлов
TEXT_CONTENT = [
    "Замечательный текст без секретов.\nВторая строка.\n",
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n",
    "Обычный документ, ничего интересного.\n",
]

CONFIG_CONTENT = [
    "server {\n    listen 8080;\n    server_name example.com;\n}\n",
    'DB_HOST = "db.example.com"\n',
    "DEBUG = false\nMAX_CONNECTIONS = 100\n",
]

SECRET_CONTENT = [
    'password = "TestPass123!"\n',
    'DB_PASSWORD = "db_secret_9"\n',
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n",
    'api_key = "a9f8c7b6e5d4c3b2a10987654321xyz"\n',
]

CODE_CONTENT = [
    'def main():\\n    print("hello")\\n\\nif __name__ == "__main__":\\n    main()\\n',
    "SELECT * FROM users WHERE id = 1;\n",
    '#!/bin/bash\\necho "hello world"\\n',
]

BINARY_BYTES = os.urandom(512)


def _write_text(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def _write_binary(path: Path, data: bytes = BINARY_BYTES):
    path.write_bytes(data)


def create_tree(branches: int = 100, depth: int = 10):
    """Создаёт структуру: branches подпапок, каждая chains depth вложенных."""
    BASE.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)  # воспроизводимость

    total_dirs = 0
    total_files = 0

    for b in range(branches):
        branch = BASE / f"branch_{b:03d}"
        cur = branch
        for level in range(depth):
            layer = cur / f"level_{level:02d}"
            layer.mkdir(parents=True, exist_ok=True)
            cur = layer
            total_dirs += 1

            # Файлы на каждом уровне
            _write_text(layer / "readme.txt", TEXT_CONTENT[level % len(TEXT_CONTENT)])
            _write_text(
                layer / "settings.cfg",
                CONFIG_CONTENT[(level + b) % len(CONFIG_CONTENT)],
            )
            _write_text(
                layer / "notes.md",
                'Обычный текст для проверки.\n`password = "secret_%d"`\n' % (b * 100 + level),
            )
            _write_binary(layer / f"img{level}.bin")

            # На уровне 3 кладём секреты
            if level == 3:
                _write_text(
                    layer / "secrets.env",
                    SECRET_CONTENT[b % len(SECRET_CONTENT)],
                )
                _write_binary(layer / "blob.dat")

            total_files += 4 if level != 3 else 5

    print(f"Создано: {total_dirs} подпапок, {total_files} файлов")
    print(f"Корень: {BASE}")


if __name__ == "__main__":
    branches = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    create_tree(branches=branches, depth=depth)
