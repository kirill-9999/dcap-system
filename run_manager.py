#!/usr/bin/env python3
"""Запуск Manager DCAP (manager.src.main:app).

Порт/хост читаются из manager/config/config.json (секция server).
Поддерживает mTLS: если в конфиге security.mtls_enabled=true и сертификаты
сгенерированы (scripts/generate_certs.py), uvicorn запускается с TLS 1.2+.

BUG-108 (v3.13.28): TLS-контекст больше не собирается вручную из путей —
используется единый CertificateManager.get_server_ssl_context(). Раньше
run_manager.py дублировал логику TLS и всегда ставил ssl_cert_reqs=CERT_OPTIONAL,
из-за чего mTLS strict был невозможен (и CRL не проверялся).
"""
import sys
import json
import uvicorn
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from manager.src.config import _resolve_env  # noqa: E402
from manager.src.core.security import CertificateManager  # noqa: E402

CONFIG_PATH = Path(__file__).parent / "manager" / "config" / "config.json"


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    server = data.get("server", {})
    return data, server.get("host", "127.0.0.1"), server.get("port", 8000)


def build_security_config(data: dict) -> dict:
    """Секция security с разрешёнными ${VAR:-default} подстановками.

    BUG-108: config.json хранит значения как "${MTLS_ENABLED:-false}";
    без _resolve_env строка считалась truthy и mTLS включался сам собой,
    а certs_dir превращался в несуществующий путь "${CERTS_DIR:-certs}".
    Приоритет явных ENV (MTLS_ENABLED/MTLS_STRICT/CERTS_DIR) применяется
    уже внутри CertificateManager — здесь только подстановки из конфига.
    """
    sec = data.get("security", {}) or {}
    resolved = {k: _resolve_env(v) for k, v in sec.items()}
    resolved.setdefault("certs_dir", "certs")
    resolved.setdefault("mtls_enabled", False)
    resolved.setdefault("mtls_strict", False)
    return resolved


def _setup_utf8():
    """UTF-8 обёртка для корректного вывода кириллицы (Windows console)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


if __name__ == "__main__":
    _setup_utf8()
    data, host, port = load_config()

    # BUG-108: единый источник TLS-конфигурации.
    cert_manager = CertificateManager(build_security_config(data))
    ssl_ctx = cert_manager.get_server_ssl_context()

    uvicorn_kwargs = {"reload": False, "log_level": "info"}

    if ssl_ctx is not None:
        uvicorn_kwargs["ssl"] = ssl_ctx
        print(
            "[run_manager] mTLS enabled ({}): Manager on https://{}:{}".format(
                "strict" if cert_manager.strict else "relaxed", host, port
            )
        )
    else:
        print("[run_manager] plain HTTP on http://{}:{} (mTLS disabled)".format(host, port))

    uvicorn.run(
        "manager.src.main:app",
        host=host,
        port=port,
        **uvicorn_kwargs,
    )
