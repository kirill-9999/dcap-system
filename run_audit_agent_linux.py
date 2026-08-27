"""Запуск Linux-агента аудита DCAP (audit-agent-linux).

Рассчитан на запуск ИЗНУТРИ Linux-окружения (audit-agent-linux).
На Windows этот скрипт лишь выводит подсказку, как запустить агент на Linux.

    cd audit-agent-linux && ./start.sh --daemon
"""
import sys
import os
from pathlib import Path


def main():
    if os.name == "nt":
        print("Linux-агент запускается на Linux, а не на Windows.")
        print("Команда внутри audit-agent-linux/:")
        print("  python main.py config.json")
        print("или")
        print("  ./start.sh --daemon")
        sys.exit(1)


if __name__ == "__main__":
    main()
