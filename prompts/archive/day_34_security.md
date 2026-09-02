📋 ТЗ — ДЕНЬ 34: БЕЗОПАСНОСТЬ (mTLS, ШИФРОВАНИЕ, СЕКРЕТЫ)
Файл: prompts/tz/day_34_security.md
Дата: 02.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Обеспечить безопасность промышленной DCAP системы на всех уровнях:

mTLS — взаимная аутентификация между всеми компонентами (Manager, WebUI, агенты, сканер)

Управление сертификатами — генерация, ротация, отзыв (CRL)

Хранение секретов — .env + Docker Secrets (интеграция в docker-compose)

Документация по безопасности — рекомендации по защите хранилищ (буферы агентов, БД)

📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
manager/src/core/
├── security.py              # НОВЫЙ: mTLS настройки, CertificateManager
└── secrets.py               # НОВЫЙ: SecretsManager (env + Docker Secrets)

manager/src/auth/
├── dependencies.py          # ОБНОВЛЕН: поддержка mTLS для агентов
└── middleware.py            # ОБНОВЛЕН: mTLS проверка для machine-эндпоинтов

shared/
├── cert_utils.py            # НОВЫЙ: общие утилиты для сертификатов
└── security.py              # НОВЫЙ: общие константы безопасности

scripts/
├── generate_certs.sh        # НОВЫЙ: генерация сертификатов
└── rotate_certs.sh          # НОВЫЙ: ротация сертификатов

audit-agent-windows/src/
├── sender.py                # ОБНОВЛЕН: поддержка mTLS
└── main.py                  # ОБНОВЛЕН: загрузка сертификатов

audit-agent-linux/src/
├── sender.py                # ОБНОВЛЕН: поддержка mTLS
└── main.py                  # ОБНОВЛЕН: загрузка сертификатов

audit-agent-s3/src/
├── sender.py                # ОБНОВЛЕН: поддержка mTLS
└── main.py                  # ОБНОВЛЕН: загрузка сертификатов

scanner/src/
├── sender.py                # ОБНОВЛЕН: поддержка mTLS
└── managed_scanner.py       # ОБНОВЛЕН: загрузка сертификатов

docker-compose.yml           # ОБНОВЛЕН: + secrets, + volumes для certs
.env.example                 # ОБНОВЛЕН: + секреты
🔐 1. mTLS — ВЗАИМНАЯ АУТЕНТИФИКАЦИЯ
1.1. Архитектура
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           mTLS В DCAP                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         CA (Certificate Authority)                  │  │
│   │                         (самоподписанный или корпоративный)         │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│              ┌───────────────┼───────────────┐                             │
│              ▼               ▼               ▼                             │
│   ┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐│
│   │   Manager         │ │   WebUI         │ │   Агенты / Scanner          ││
│   │   (серверный      │ │   (клиентский   │ │   (клиентские сертификаты)  ││
│   │   сертификат)     │ │   сертификат)   │ │                             ││
│   └───────────────────┘ └─────────────────┘ └─────────────────────────────┘│
│                                                                             │
│   Взаимодействие:                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  Агент → Manager:  mTLS (агент проверяет Manager, Manager — агента) │  │
│   │  WebUI → Manager:  mTLS (WebUI проверяет Manager)                  │  │
│   │  Scanner → Manager: mTLS (Scanner проверяет Manager)               │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
1.2. Структура сертификатов
bash
certs/
├── ca/
│   ├── ca.crt               # Корневой сертификат CA
│   └── ca.key               # Приватный ключ CA (хранить в секрете!)
├── manager/
│   ├── manager.crt          # Серверный сертификат Manager
│   └── manager.key          # Приватный ключ Manager
├── webui/
│   ├── webui.crt            # Клиентский сертификат WebUI
│   └── webui.key            # Приватный ключ WebUI
├── agents/
│   ├── agent-windows.crt    # Сертификат Windows-агента
│   ├── agent-windows.key
│   ├── agent-linux.crt      # Сертификат Linux-агента
│   ├── agent-linux.key
│   ├── agent-s3.crt         # Сертификат S3-агента
│   └── agent-s3.key
├── scanner/
│   ├── scanner.crt          # Сертификат сканера
│   └── scanner.key
└── crl/
    └── crl.pem              # Certificate Revocation List
1.3. Генерация сертификатов
bash
# scripts/generate_certs.sh
#!/bin/bash
# Генерация всех сертификатов для DCAP

set -e

CA_DIR="./certs/ca"
MANAGER_DIR="./certs/manager"
WEBUI_DIR="./certs/webui"
AGENTS_DIR="./certs/agents"
SCANNER_DIR="./certs/scanner"
CRL_DIR="./certs/crl"

mkdir -p $CA_DIR $MANAGER_DIR $WEBUI_DIR $AGENTS_DIR $SCANNER_DIR $CRL_DIR

# ===== 1. CA =====
openssl genrsa -out $CA_DIR/ca.key 4096
openssl req -x509 -new -nodes -key $CA_DIR/ca.key -sha256 -days 3650 \
    -out $CA_DIR/ca.crt \
    -subj "/CN=DCAP-CA/OU=Security/O=DCAP"

# ===== 2. Manager (серверный) =====
openssl genrsa -out $MANAGER_DIR/manager.key 2048
openssl req -new -key $MANAGER_DIR/manager.key \
    -out $MANAGER_DIR/manager.csr \
    -subj "/CN=manager.dcap.local/OU=Manager/O=DCAP"
openssl x509 -req -in $MANAGER_DIR/manager.csr \
    -CA $CA_DIR/ca.crt -CAkey $CA_DIR/ca.key -CAcreateserial \
    -out $MANAGER_DIR/manager.crt -days 365 -sha256 \
    -extfile <(cat <<EOF
subjectAltName=DNS:manager,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0
EOF
)

# ===== 3. WebUI =====
openssl genrsa -out $WEBUI_DIR/webui.key 2048
openssl req -new -key $WEBUI_DIR/webui.key \
    -out $WEBUI_DIR/webui.csr \
    -subj "/CN=webui.dcap.local/OU=WebUI/O=DCAP"
openssl x509 -req -in $WEBUI_DIR/webui.csr \
    -CA $CA_DIR/ca.crt -CAkey $CA_DIR/ca.key -CAcreateserial \
    -out $WEBUI_DIR/webui.crt -days 365 -sha256 \
    -extfile <(cat <<EOF
subjectAltName=DNS:webui,DNS:localhost,IP:127.0.0.1
EOF
)

# ===== 4. Агенты =====
for agent in agent-windows agent-linux agent-s3; do
    openssl genrsa -out $AGENTS_DIR/${agent}.key 2048
    openssl req -new -key $AGENTS_DIR/${agent}.key \
        -out $AGENTS_DIR/${agent}.csr \
        -subj "/CN=${agent}/OU=Agents/O=DCAP"
    openssl x509 -req -in $AGENTS_DIR/${agent}.csr \
        -CA $CA_DIR/ca.crt -CAkey $CA_DIR/ca.key -CAcreateserial \
        -out $AGENTS_DIR/${agent}.crt -days 365 -sha256
done

# ===== 5. Scanner =====
openssl genrsa -out $SCANNER_DIR/scanner.key 2048
openssl req -new -key $SCANNER_DIR/scanner.key \
    -out $SCANNER_DIR/scanner.csr \
    -subj "/CN=scanner/OU=Scanner/O=DCAP"
openssl x509 -req -in $SCANNER_DIR/scanner.csr \
    -CA $CA_DIR/ca.crt -CAkey $CA_DIR/ca.key -CAcreateserial \
    -out $SCANNER_DIR/scanner.crt -days 365 -sha256

# ===== 6. CRL =====
openssl ca -gencrl -keyfile $CA_DIR/ca.key -cert $CA_DIR/ca.crt \
    -out $CRL_DIR/crl.pem -config <(cat <<EOF
[ ca ]
default_ca = CA_default
[ CA_default ]
database = $CA_DIR/index.txt
EOF
)

echo "✅ All certificates generated successfully!"
1.4. CertificateManager
python
# manager/src/core/security.py
import ssl
import os
from pathlib import Path
from typing import Optional, Tuple
import logging
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

class CertificateManager:
    """Управление сертификатами для mTLS"""
    
    def __init__(self, config: dict):
        self.config = config
        self.certs_dir = Path(config.get("certs_dir", "certs"))
        self.ca_cert_path = self.certs_dir / "ca" / "ca.crt"
        self.manager_cert_path = self.certs_dir / "manager" / "manager.crt"
        self.manager_key_path = self.certs_dir / "manager" / "manager.key"
        self.crl_path = self.certs_dir / "crl" / "crl.pem"
        
        self._validate_files()
    
    def _validate_files(self):
        """Проверка наличия файлов сертификатов"""
        required = [self.ca_cert_path, self.manager_cert_path, self.manager_key_path]
        for path in required:
            if not path.exists():
                raise FileNotFoundError(f"Certificate file not found: {path}")
    
    def get_ssl_context(self, require_client_cert: bool = True) -> ssl.SSLContext:
        """Создание SSL контекста для mTLS"""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Загрузка сертификата Manager
        context.load_cert_chain(
            str(self.manager_cert_path),
            str(self.manager_key_path)
        )
        
        # Загрузка CA
        context.load_verify_locations(str(self.ca_cert_path))
        
        # Требование клиентского сертификата
        if require_client_cert:
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_OPTIONAL
        
        # Настройка шифров
        context.set_ciphers("ECDHE+AESGCM:!aNULL:!eNULL")
        
        # Загрузка CRL (если есть)
        if self.crl_path.exists():
            context.load_verify_locations(cafile=str(self.crl_path))
        
        return context
    
    def verify_client_cert(self, cert_der: bytes) -> Tuple[bool, Optional[str]]:
        """Проверка клиентского сертификата"""
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            
            # Проверка подписи CA
            # (реализация)
            
            # Извлечение CN
            cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn:
                return True, cn[0].value
            
            return False, None
            
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}")
            return False, None
    
    def is_revoked(self, serial: str) -> bool:
        """Проверка отзыва сертификата"""
        if not self.crl_path.exists():
            return False
        
        try:
            with open(self.crl_path, 'rb') as f:
                crl = x509.load_pem_x509_crl(f.read(), default_backend())
            
            for revoked in crl:
                if revoked.serial_number == int(serial, 16):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"CRL check failed: {e}")
            return False
1.5. Middleware для mTLS
python
# manager/src/auth/middleware.py (ОБНОВЛЕННЫЙ)

from ..core.security import CertificateManager

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_manager, db_session_factory, cert_manager: CertificateManager):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.db_session_factory = db_session_factory
        self.cert_manager = cert_manager
    
    async def dispatch(self, request: Request, call_next):
        # ... существующая логика ...
        
        # Проверка mTLS для machine-эндпоинтов (агенты, сканер)
        if self._is_machine_endpoint(request.url.path):
            # Получение клиентского сертификата из SSL контекста
            client_cert = request.scope.get("client_cert")
            if client_cert:
                is_valid, cn = self.cert_manager.verify_client_cert(client_cert)
                if is_valid and cn:
                    request.state.client_cert_cn = cn
                    return await call_next(request)
                else:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid client certificate"}
                    )
            else:
                # Если mTLS включен, но сертификат не предоставлен
                if self.cert_manager.config.get("mtls_required", False):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Client certificate required"}
                    )
        
        return await call_next(request)
    
    def _is_machine_endpoint(self, path: str) -> bool:
        """Проверка: эндпоинт для агентов/сканеров"""
        machine_paths = [
            "/api/audit/events",
            "/api/audit/agents/heartbeat",
            "/api/audit/agents/register",
            "/api/audit/permissions",
            "/api/scanner/register",
            "/api/scanner/heartbeat",
            "/api/scanner/tasks/pending",
            "/api/scanner/results",
        ]
        return any(path.startswith(p) for p in machine_paths)
1.6. Агенты — поддержка mTLS
python
# audit-agent-windows/src/sender.py (ОБНОВЛЕННЫЙ)

class Sender:
    def __init__(self, config: dict):
        self.manager_url = config["manager"]["url"].rstrip("/")
        # ...
        
        # mTLS настройки
        cert_path = config.get("cert_path")
        key_path = config.get("key_path")
        ca_path = config.get("ca_path")
        
        self.session = requests.Session()
        if cert_path and key_path and ca_path:
            self.session.cert = (cert_path, key_path)
            self.session.verify = ca_path
            logger.info("mTLS enabled for sender")
        else:
            # Fallback на обычный HTTP (для разработки)
            logger.warning("mTLS not configured, using plain HTTP")
1.7. Manager — запуск с mTLS
python
# manager/src/main.py (ОБНОВЛЕННЫЙ)

from .core.security import CertificateManager

def create_app():
    app = FastAPI(...)
    
    # Инициализация CertificateManager
    cert_manager = CertificateManager(config)
    
    # Создание SSL контекста для uvicorn
    ssl_context = cert_manager.get_ssl_context(require_client_cert=True)
    
    return app, ssl_context

# В run_manager.py:
if __name__ == "__main__":
    app, ssl_context = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
        ssl_ca_certs=ca_path,
        ssl_cert_reqs=ssl.CERT_REQUIRED
    )
1.8. docker-compose.yml — mTLS
yaml
# docker-compose.yml (дополнение)

services:
  manager:
    # ...
    volumes:
      - ./certs/manager:/app/certs/manager:ro
      - ./certs/ca:/app/certs/ca:ro
      - ./certs/crl:/app/certs/crl:ro
    environment:
      - MTLS_ENABLED=true
      - CERT_PATH=/app/certs/manager/manager.crt
      - KEY_PATH=/app/certs/manager/manager.key
      - CA_PATH=/app/certs/ca/ca.crt

  s3-agent:
    # ...
    volumes:
      - ./certs/agents/agent-s3.crt:/app/certs/agent.crt:ro
      - ./certs/agents/agent-s3.key:/app/certs/agent.key:ro
      - ./certs/ca:/app/certs/ca:ro
    environment:
      - MTLS_ENABLED=true
      - CERT_PATH=/app/certs/agent.crt
      - KEY_PATH=/app/certs/agent.key
      - CA_PATH=/app/certs/ca/ca.crt
🔒 2. ХРАНЕНИЕ СЕКРЕТОВ
2.1. SecretsManager
python
# manager/src/core/secrets.py
import os
import json
from pathlib import Path
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class SecretsManager:
    """Управление секретами (env + Docker Secrets)"""
    
    def __init__(self, config: dict):
        self.config = config
        self.secrets_dir = Path(config.get("secrets_dir", "/run/secrets"))
        self.cache = {}
    
    def get(self, key: str, default: Any = None) -> Optional[str]:
        """
        Получение секрета по ключу.
        Приоритет: Docker Secrets > env > default
        """
        if key in self.cache:
            return self.cache[key]
        
        # 1. Docker Secrets
        secret_path = self.secrets_dir / key.lower().replace("_", "")
        if secret_path.exists():
            try:
                with open(secret_path, 'r') as f:
                    value = f.read().strip()
                    self.cache[key] = value
                    return value
            except Exception as e:
                logger.debug(f"Error reading Docker secret {key}: {e}")
        
        # 2. Переменные окружения
        value = os.environ.get(key)
        if value is not None:
            self.cache[key] = value
            return value
        
        # 3. Default
        return default
    
    def get_required(self, key: str) -> str:
        """Получение обязательного секрета (если нет — ошибка)"""
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required secret not found: {key}")
        return value
2.2. docker-compose.yml — Secrets
yaml
# docker-compose.yml (дополнение)

secrets:
  jwt_secret_key:
    file: ./secrets/jwt_secret_key.txt
  db_password:
    file: ./secrets/db_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  s3_access_key:
    file: ./secrets/s3_access_key.txt
  s3_secret_key:
    file: ./secrets/s3_secret_key.txt
  ad_service_password:
    file: ./secrets/ad_service_password.txt
  agent_encryption_key:
    file: ./secrets/agent_encryption_key.txt

services:
  manager:
    # ...
    secrets:
      - jwt_secret_key
      - db_password
      - redis_password
      - ad_service_password
    environment:
      - JWT_SECRET_KEY_FILE=/run/secrets/jwt_secret_key
      - DB_PASSWORD_FILE=/run/secrets/db_password
      - REDIS_PASSWORD_FILE=/run/secrets/redis_password

  s3-agent:
    # ...
    secrets:
      - s3_access_key
      - s3_secret_key
    environment:
      - S3_ACCESS_KEY_FILE=/run/secrets/s3_access_key
      - S3_SECRET_KEY_FILE=/run/secrets/s3_secret_key
2.3. .env.example (обновленный)
bash
# .env.example — секреты (локальная разработка)

# ===== JWT =====
JWT_SECRET_KEY=change-me-in-production-32-chars-long

# ===== База данных =====
DB_PASSWORD=dcap123

# ===== Redis =====
REDIS_PASSWORD=redis123

# ===== S3 =====
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key

# ===== AD =====
AD_SERVICE_PASSWORD=Passw0rd

# ===== Агент шифрование =====
AGENT_ENCRYPTION_KEY=change-me-in-production
2.4. secrets/ (директория для Docker Secrets)
bash
secrets/
├── jwt_secret_key.txt          # JWT_SECRET_KEY
├── db_password.txt             # DB_PASSWORD
├── redis_password.txt          # REDIS_PASSWORD
├── s3_access_key.txt           # S3_ACCESS_KEY
├── s3_secret_key.txt           # S3_SECRET_KEY
├── ad_service_password.txt     # AD_SERVICE_PASSWORD
└── agent_encryption_key.txt    # AGENT_ENCRYPTION_KEY
📋 3. ДОКУМЕНТАЦИЯ ПО БЕЗОПАСНОСТИ
3.1. SECURITY.md
markdown
# Политика безопасности DCAP System

## Поддерживаемые версии

| Версия | Поддерживается |
|--------|----------------|
| 3.0.x   | ✅ |
| 2.1.x   | ❌ |

## Рекомендации по безопасности

### 1. mTLS

- **Все компоненты должны использовать mTLS** в production окружении
- Генерация сертификатов через `scripts/generate_certs.sh`
- Ротация сертификатов — каждые 90 дней
- Использование CRL для отзыва компрометированных сертификатов

### 2. Хранение секретов

- **Никогда не храните секреты в коде**
- Используйте Docker Secrets в production
- Используйте .env только для разработки
- Регулярная ротация паролей и ключей

### 3. Шифрование буферов агентов

Рекомендации по защите буферов:

**Windows Agent:**
- Используйте EFS (Encrypting File System) для директории `data/buffer/`
- Используйте BitLocker для всего диска

**Linux Agent:**
- Используйте LUKS для шифрования диска
- Используйте eCryptfs или fscrypt для директории `data/buffer/`

**S3 Agent:**
- Используйте SSE-S3 или SSE-KMS для S3-бакетов с логами
- Используйте клиентское шифрование для буфера

### 4. База данных (PostgreSQL)

- Используйте TLS для подключения к БД
- Включите шифрование на уровне диска
- Настройте сетевые политики (firewall)
- Регулярное резервирование

### 5. Сеть

- Все компоненты должны работать в изолированной сети
- Используйте VPN для удаленного доступа
- Ограничьте доступ к портам (firewall)

## Компрометация секретов

При компрометации:

1. Остановите затронутые компоненты
2. Отзовите сертификаты (CRL)
3. Сгенерируйте новые секреты
4. Перезапустите компоненты
5. Проверьте логи на наличие подозрительной активности

## Ответственное раскрытие

Если вы нашли уязвимость:

1. **Не создавайте публичный Issue**
2. Напишите на email: security@dcap.local
3. Мы ответим в течение 48 часов
3.2. docs/security_checklist.md
markdown
# Чеклист безопасности для production

## Перед развертыванием

- [ ] Сгенерированы сертификаты (`scripts/generate_certs.sh`)
- [ ] Сертификаты скопированы в защищенное хранилище
- [ ] Созданы Docker Secrets для всех паролей
- [ ] JWT_SECRET_KEY заменен на уникальную строку
- [ ] Пароль admin изменен (admin/admin123)

## Настройка компонентов

- [ ] mTLS включен для Manager
- [ ] mTLS включен для WebUI
- [ ] mTLS включен для всех агентов
- [ ] mTLS включен для сканера
- [ ] Docker Secrets подключены

## Мониторинг

- [ ] Логирование включено для всех компонентов
- [ ] Алерты настроены на подозрительную активность
- [ ] Аудит включен (все API запросы логируются)

## Резервирование

- [ ] Резервное копирование БД настроено
- [ ] Резервное копирование сертификатов настроено
- [ ] План восстановления задокументирован
✅ КРИТЕРИИ ПРИЕМКИ
mTLS
□ Скрипт генерации сертификатов создан и работает
□ Manager принимает mTLS соединения
□ WebUI подключается к Manager через mTLS
□ Windows-агент подключается через mTLS
□ Linux-агент подключается через mTLS
□ S3-агент подключается через mTLS
□ Scanner подключается через mTLS
□ CRL работает (отзыв сертификатов)
Секреты
□ SecretsManager поддерживает env + Docker Secrets
□ docker-compose.yml использует Docker Secrets
□ .env.example обновлен
□ Все секреты вынесены из кода
Документация
□ SECURITY.md создан
□ docs/security_checklist.md создан
□ AGENTS.md обновлен (mTLS инструкции)
□ README.md обновлен
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Генерация сертификатов
./scripts/generate_certs.sh

# 2. Создание секретов
mkdir -p secrets
echo "your-jwt-secret" > secrets/jwt_secret_key.txt
echo "dcap123" > secrets/db_password.txt

# 3. Запуск с mTLS
docker-compose up -d

# 4. Проверка mTLS
curl --cert certs/agents/agent-s3.crt --key certs/agents/agent-s3.key \
     --cacert certs/ca/ca.crt \
     https://localhost:8000/api/audit/events

# 5. Проверка отзыва сертификата
# (добавить в CRL, повторить запрос → должен быть отклонен)
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_34_security
git add .
git commit -m "feat: День 34 — Безопасность (mTLS, секреты, документация)

mTLS:
- Генерация сертификатов (scripts/generate_certs.sh)
- CertificateManager (Manager)
- mTLS поддержка во всех агентах и сканере
- CRL для отзыва сертификатов
- Middleware для проверки mTLS

Секреты:
- SecretsManager (env + Docker Secrets)
- docker-compose.yml с Docker Secrets
- .env.example обновлен

Документация:
- SECURITY.md — политика безопасности
- docs/security_checklist.md — чеклист для production
- AGENTS.md, README.md обновлены"
This response is AI-generated, for reference only.
