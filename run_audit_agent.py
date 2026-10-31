"""Запуск Windows-агента аудита DCAP (audit-agent-windows).

Агент — не пакет (внутри `audit-agent-windows/main.py` топ-уровневые импорты
collector/buffer/sender), поэтому его каталог добавляется в sys.path.
Конфиг обязателен, без него запуск невозможен.

    python run_audit_agent.py audit-agent-windows/config.json
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
AGENT_DIR = ROOT / "audit-agent-windows"


def main():
    if len(sys.argv) < 2:
        print("? Ошибка: не указан путь к конфигурационному файлу")
        print("Использование: python run_audit_agent.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"? Ошибка: конфиг не найден: {config_path}")
        sys.exit(1)

    sys.path.insert(0, str(AGENT_DIR))
    import main as agent_main

    agent_main.run(config_path)


if __name__ == "__main__":
    main()
