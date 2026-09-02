#!/usr/bin/env python3
"""Запуск Manager DCAP (manager.src.main:app).

Порт/хост читаются из manager/config/config.json (секция server).
Поддерживает mTLS: если в конфиге security.mtls_enabled=true и сертификаты
сгенерированы (scripts/generate_certs.py), uvicorn запускается с TLS 1.2+.
"""
import sys
import json
import ssl
import uvicorn
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "manager" / "config" / "config.json"


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    server = data.get("server", {})
    return data, server.get("host", "127.0.0.1"), server.get("port", 8000)


if __name__ == "__main__":
    data, host, port = load_config()

    security = data.get("security", {})
    mtls_enabled = security.get("mtls_enabled", False)
    certs_dir = Path(security.get("certs_dir", "certs"))
    ca_path = certs_dir / "ca" / "ca.crt"
    cert_path = certs_dir / "manager" / "manager.crt"
    key_path = certs_dir / "manager" / "manager.key"

    uvicorn_kwargs = {"reload": False, "log_level": "info"}

    if mtls_enabled and all(p.exists() for p in (cert_path, key_path, ca_path)):
        uvicorn_kwargs.update(
            {
                "ssl_keyfile": str(key_path),
                "ssl_certfile": str(cert_path),
                "ssl_ca_certs": str(ca_path),
                "ssl_cert_reqs": ssl.CERT_OPTIONAL,  # OPTIONAL = relaxed mTLS
                "ssl_ciphers": "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS",
            }
        )
        print("[run_manager] mTLS enabled: Manager on https://{}:{}".format(host, port))
    else:
        print("[run_manager] plain HTTP on http://{}:{} (mTLS disabled)".format(host, port))

    uvicorn.run(
        "manager.src.main:app",
        host=host,
        port=port,
        **uvicorn_kwargs,
    )