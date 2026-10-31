"""Общие константы безопасности для DCAP."""

# Минимальная версия TLS
MIN_TLS_VERSION = "TLSv1.2"

# Разрешённые шифры (ECDHE + AES-GCM/ChaCha20)
ALLOWED_CIPHERS = (
    "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
)

# Срок жизни сертификатов (дни)
CERT_VALIDITY_DAYS_CA = 3650       # CA — 10 лет
CERT_VALIDITY_DAYS_COMPONENT = 365 # Компоненты — 1 год
CERT_KEY_SIZE_CA = 4096
CERT_KEY_SIZE_COMPONENT = 2048

# Описание компонентов DCAP
DCAP_COMPONENTS = {
    "ca": {"cn": "DCAP-CA", "ou": "Security", "o": "DCAP"},
    "manager": {"cn": "manager.dcap.local", "ou": "Manager", "o": "DCAP"},
    "webui": {"cn": "webui.dcap.local", "ou": "WebUI", "o": "DCAP"},
    "agent-windows": {"cn": "agent-windows", "ou": "Agents", "o": "DCAP"},
    "agent-linux": {"cn": "agent-linux", "ou": "Agents", "o": "DCAP"},
    "agent-s3": {"cn": "agent-s3", "ou": "Agents", "o": "DCAP"},
    "scanner": {"cn": "scanner", "ou": "Scanner", "o": "DCAP"},
}

# SAN (Subject Alternative Names) для серверных сертификатов
COMPONENT_SANS = {
    "manager": "DNS:manager,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0",
    "webui": "DNS:webui,DNS:localhost,IP:127.0.0.1",
}

# Файловые расширения сертификатов
CERT_EXTENSIONS = {
    "ca_cert": ".crt",
    "ca_key": ".key",
    "cert": ".crt",
    "key": ".key",
    "csr": ".csr",
    "crl": ".pem",
}
