# Чеклист безопасности для production

## Перед развертыванием

- [ ] Сгенерированы сертификаты (`python scripts/generate_certs.py`)
- [ ] Сертификаты скопированы в защищенное хранилище
- [ ] Созданы Docker Secrets для всех паролей
- [ ] `JWT_SECRET_KEY` заменен на уникальную строку
- [ ] Пароль admin изменен (из `admin/admin123`)

## Настройка компонентов

- [ ] mTLS включен для Manager
- [ ] mTLS включен для WebUI
- [ ] mTLS включен для всех агентов
- [ ] mTLS включен для сканера
- [ ] Docker Secrets подключены

## Генерация PKI

```bash
python scripts/generate_certs.py
# структура certs/:
#   ca/ca.crt + ca/ca.key (ключ CA — в секрете!)
#   manager/manager.{crt,key}
#   webui/webui.{crt,key}
#   agents/agent-windows.{crt,key}, agent-linux, agent-s3
#   scanner/scanner.{crt,key}
#   crl/crl.pem
```

## Конфигурация mTLS (manager/config/config.json)

```json
{
    "security": {
        "mtls_enabled": true,
        "mtls_strict": false
    }
}
```

## Проверка mTLS (curl)

```bash
curl --cert certs/agents/agent-s3.crt --key certs/agents/agent-s3.key \
     --cacert certs/ca/ca.crt \
     https://localhost:8000/api/audit/events
```

## Мониторинг

- [ ] Логирование включено для всех компонентов
- [ ] Алерты настроены на подозрительную активность
- [ ] Аудит включен (все API-запросы логируются)

## Резервирование

- [ ] Резервное копирование БД настроено
- [ ] Резервное копирование сертификатов настроено
- [ ] План восстановления задокументирован