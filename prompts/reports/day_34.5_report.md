# Отчёт: День 34.5 — Интеграция Secret Scanner в DCAP

**Дата:** 09.09.2026
**ТЗ:** `prompts/tz/day_34.5_secret_scanner_integration.md`
**Роль:** Кодер
**Версия:** v3.4.0 (в ТЗ указано «v3.0.0» — исторический артефакт, проект на момент старта v3.3.0, см. обратную связь)

---

## Резюме

Перенесены наработки стендэлон-утилиты `dcap-secret-scanner` в основной `scanner/` DCAP:

- **FP-фильтры** — подавление ложных срабатываний: плейсхолдеры (`your_*`, `example`, `changeme`, `password1`, `<PASSWORD>`, `NNN_KEY`), строки-комментарии (`#`, `//`, `;`, `*`, `--`, `<!--`), дамп-значения (только цифры/hex/один регистр).
- **Префильтр** — один скомпилированный regex по всем паттернам вместо множества проходов; файлы без совпадений не анализируются детально.
- **Расширение типов файлов** — `.pem/.key/.crt/.csr/.p12/.pfx/.jks/.env/.envrc`, Office `.doc/.xls` (через `DocumentExtractor`: catdoc/xlrd) в дополнение к существующим.
- **Буферизованное чтение** — чтение по 1 МБ вместо `f.read()` целиком; лимит 200 000 символов для текстовых файлов.
- **Детекция по имени файла** — `id_rsa`, `.netrc`, `.pgpass`, `kubeconfig`, `.env`, `secrets` и др. сканируются по имени (вне зависимости от расширения) и помечаются `CRED_*` находками.
- **Текстовый лог-отчёт** — `generate_report()` без значений секретов (маскирование `mask_value`), группировка по категориям, секция ошибок.

> **Адаптации под реальную архитектуру (расхождения с буквой ТЗ):**
> - Пути в ТЗ (`scanner/src/classifiers/...`, `scanner/src/connectors/...`, `scanner/src/core/orchestrator.py`, `scanner/src/handlers/finding_collector.py`) не существуют в репо — реальные: `scanner/classifiers/`, `scanner/connectors/`, `scanner/core/orchestrator.py`, `scanner/handlers/finding_collector.py`. Маппинг выполнен на реальные пути.
> - `orchestrator.py` в ТЗ указан «Интеграция новых фильтров» — отдельной правки не потребовалось: фильтры и префильтр работают внутри классификатора, а новые параметры коннектора доходят через `managed_scanner._get_connector_config()`.
> - **DUMP_PATTERNS из ТЗ умышленно уточнены**: паттерны `^[A-Z0-9]{16,}$`/`^[a-z0-9]{16,}$`/`^[A-Za-z]{16,}$`/`^[0-9a-fA-F]{32,}$` отбрасывали бы настоящие секреты в верхнем регистре+цифры (AWS `AKIA…`, GitHub `ghp_…`) и длинные hex-хеши (SHA-256 — это и есть секреты). Оставлены безопасные варианты (`^\d+$`, «цифры/иксы» `^[0-9x]+$`, короткий hex `{8,16}`, один регистр буквами `{16,}`) + whitelist сигнатурных префиксов (`AKIA/ASIA/ghp_/ghs_/gho_/xox/eyJ/-----BEGIN/sk-`), проверено тестом, что AWS-ключ реально детектится.
> - `config.scanner` уровня `scanner_config.json` не менялся (schema same); новые параметры добавляются в секции `credentials_classifier` и `connector` без `require`.

---

## Ключевые решения по коду

- **Фильтры в классификаторе, а не в коннекторе**: префильтр и FP-фильтры работают над текстом → живут в `credentials_classifier.py`, как и в утилите. Скип директорий-образцов — в коннекторе (`filesystem.py`), т.к. это задача обхода ФС.
- **`_apply_filters(value, line)`** — единая точка: min_length → placeholder → dump → comment (по строке, где найден `match.start()`) → require_mixed. Энтропия, как и раньше, применяется только к правилам с `check_entropy=True` (иначе SSH-ключи `-----BEGIN…` с низкой энтропией терялись бы).
- **Префильтр**: `_compile_prefilter()` собирает `'|'.join(f'({p})')` по всем паттернам, `re.IGNORECASE | re.MULTILINE`; `prefilter(text)` — путь выхода до детального анализа. Файлы-креды по имени обрабатываются ДО префильтра (находка `CRED_*` остаётся даже если текст пуст).
- **Буферизация**: `get_content` читает по `buffer_size`; для текстовых расширений останавливается после накопления `max_text_chars` байт (дальше классификатору не нужно). Бинарные/Office-файлы читаются целиком (нужны для разбора). Классификатор дополнительно режет декодированный текст до 200 000 символов.
- **Файлы по имени**: единый набор `CRED_FILENAMES` в `filesystem.py` (для включения в `list_files` без расширения) и `CRED_FILE_NAMES` → subcategory в классификаторе; `_get_text` обрабатывает такие имена как текст независимо от расширения.
- **`shared/event_schema.py`**: добавлена константа `SCANNER_CREDENTIAL_SUBCATEGORIES` — единый перечень `CRED_*` подкатегорий находок сканера (находки уезжают в `metadata["findings"]`).

---

## Выполненная работа

### 1. FP-фильтры (MODIFIED)

**`scanner/classifiers/credentials_classifier.py`** (v1.1):
- `PLACEHOLDER_PATTERNS` — 15 паттернов плейсхолдеров (`your_*`, `example_*`, `changeme`, `<PASSWORD>`, `{{PASSWORD}}`, `xxx+`, `[0-9x]{8,}`, `NNN[_-]?[A-Z]+`, `password\d{1,2}`, `admin\d{1,2}`, `test_*`, `sample_*`, `demo_*`, `example.com`, `changeme.com`).
- `COMMENT_PATTERNS` — маркеры начала строки (`#`, `//`, `;`, `*`, `--`, `<!--`).
- `DUMP_PATTERNS` — дамп-значения (безопасный набор, см. резюме) + `SIGNATURE_PREFIXES`.
- Методы: `_is_placeholder`, `_is_comment_line`, `_is_dump_value`, `_has_mixed_case`, `_apply_filters`, `_line_at`.
- `strict_filter` (default True) управляет включением дум-фильтра; `min_length` (8), `min_entropy` (4.5 через `entropy_threshold`), `confidence_threshold` (0.7), `no_generic`, `require_mixed` — новые настройки `configure()`.

### 2. Префильтр (MODIFIED, тот же файл)

- `_compile_prefilter()` + `prefilter(content)`; в `classify()` — ранний выход (`return` с сохранённой filename-находкой), если ни один паттерн не встретился.

### 3. Расширение типов файлов (MODIFIED)

- **`scanner/connectors/filesystem.py`**: расширен дефолтный список `extensions` (67 шт.) — +pem/key/crt/csr/cert/p12/pfx/jks, env/envrc/properties, dockerfile/makefile/tf/hcl, doc/xls, tiff/webp и др.
- **`scanner/classifiers/credentials_classifier.py`**: расширены `text_exts`, добавлена обработка `.pem/.key/.crt/.p12/.pfx/.jks` как текста и `.doc/.xls/.xlsx/.docx/.pdf` через `DocumentExtractor`.
- **`scanner/src/config_loader.py`**: `DEFAULT_EXTENSIONS`/`DEFAULT_SKIP_DIRS` как константы модуля; `ConnectorConfig.buffer_size` (1 МБ) и `max_text_chars` (200 000).

### 4. Буферизованное чтение (MODIFIED)

- **`scanner/connectors/filesystem.py`**: `get_content` — чтение чанками по `buffer_size`; для текстовых расширений остановка после `max_text_chars` байт.
- **`scanner/src/managed_scanner.py`**: `_get_connector_config()` прокидывает `buffer_size`/`max_text_chars` в коннектор.

### 5. Детекция по имени файла (NEW logic)

- **`scanner/connectors/filesystem.py`**: `CRED_FILENAMES` (id_rsa/dsa/ecdsa/ed25519, .pgpass, .netrc, kubeconfig, jaas.conf, secrets*, .env*, .htpasswd, passwd, shadow, .npmrc, .pypirc, .gemrc, .boto, .my.cnf, .my.ini, .gitignore/… ) — файлы включаются в `list_files` даже без расширения из списка.
- **`scanner/classifiers/credentials_classifier.py`**: `CRED_FILE_NAMES` → `CRED_*` subcategory, `_credential_file_finding()` (confidence 0.9, detection_method `filename`), `_get_text` для таких имён декодирует как текст.

### 6. Текстовый лог-отчёт (MODIFIED)

**`scanner/handlers/finding_collector.py`**:
- `mask_value(value, keep=4)` — маскирование (`AKIA****…`) без утечки секретов.
- `generate_report(file_path=None)` — шапка (время, счётчики, длительность), `BY CATEGORY`-статистика, находки сгруппированы по категориям (`== CREDENTIALS ==`), `IN VALUES MASKED`, секция `[FAILED TO PROCESS]` (до 50 файлов), без значений секретов.

### 7. Конфигурация (MODIFIED)

- **`scanner/config/scanner_config.json`**: `credentials_classifier` — `entropy_threshold: 4.5`, `min_length: 8`, `strict_filter: true`, `confidence_threshold: 0.7`, `no_generic: false`, `require_mixed: false`, `max_file_size_mb: 50`; `connector` — расширенный `skip_dirs` (+`_example/sample/template/examples/samples/templates/.git/models`), `buffer_size: 1048576`, `max_text_chars: 200000`.
- **`scanner/src/config_loader.py`**: `CredentialsConfig` (+strict_filter/min_length/confidence_threshold/no_generic/require_mixed), `ConnectorConfig` (+buffer_size/max_text_chars), синхронизация `to_dict`/`from_dict`, `__all__`.
- **`scanner/src/managed_scanner.py`**: `cred_config_dict` теперь передаёт все новые параметры классификатору.

### 8. Event Schema (MODIFIED)

**`shared/event_schema.py`**: добавлена `SCANNER_CREDENTIAL_SUBCATEGORIES` (25 подкатегорий `CRED_*`).

---

## Тестирование

Скрипт `temp/test_day_34_5.py` (58 проверок, PASS=58 FAIL=0):

- **Импорт** всех изменённых модулей (без тяжёлого `classifiers/__init__` → pii/spacy: этот импорт тянет spacy/presidio и висит — не связано с правкой, пресуществующее поведение).
- **config_loader**: 67 расширений, наличие pem/key/crt/env/doc/xls/p12/pfx/jks; `skip_dirs` содержит sample/template; дефолты strict_filter/min_length/confidence_threshold; реальный `scanner_config.json` грузится, новые поля доезжают.
- **FP-фильтры**: плейсхолдеры отброшены (`your_password`, `changeme`, `password12`, `<PASSWORD>`, `xxx`, `12345678`); реальный пароль `Tr0ub4dor&3` сохранён; комментарии всех видов отброшены; дампы (цифры/hex/заглавные-буквы) отброшены; AWS `AKIA…` и GH `ghp_…` НЕ отброшены (signature whitelist); `min_length` работает.
- **Префильтр**: чистый текст → False; `api_key = …` и SSH-ключ → True.
- **classify**: в тексте найден `CRED_AWS_ACCESS_KEY` + `CRED_AWS_SECRET_KEY` (пример из AWS Docs реально детектится); `id_rsa` → `CRED_SSH_PRIVATE_KEY`; `.env` → `CRED_ENV_FILE`.
- **Лог-отчёт**: секции «values masked», `[FAILED TO PROCESS]`, текст ошибки, группировка `== CREDENTIALS ==`; значение в отчёте замаскировано (`value=AKIA…` → `AKIA****…`).
- **Коннектор**: `list_files` находит `kubeconfig` и `.env.local` по имени (без расширения в списке), `notes.txt` по расширению; `get_content` буферизован; связка «коннектор → классификатор» для `id_rsa` даёт `CRED_SSH_PRIVATE_KEY`.

### Проверка сборки

- `python -m py_compile` всех 6 изменённых файлов — без ошибок.
- `python temp/test_day_34_5.py` — **58 passed**.

---

## Файлы

**Modified:**
- `scanner/classifiers/credentials_classifier.py` (v1.1: FP-фильтры, префильтр, CRED_FILE_NAMES, doc/xls, extended text_exts)
- `scanner/connectors/filesystem.py` (CRED_FILENAMES, extended extensions/skip_dirs, бufferized get_content)
- `scanner/handlers/finding_collector.py` (mask_value, generate_report)
- `scanner/src/config_loader.py` (CredentialsConfig/ConnectorConfig новые поля, DEFAULT_EXTENSIONS/SKIP_DIRS)
- `scanner/src/managed_scanner.py` (проброс параметров классификатора и коннектора)
- `scanner/config/scanner_config.json` (новые параметры)
- `shared/event_schema.py` (SCANNER_CREDENTIAL_SUBCATEGORIES)
- `AGENTS.md` (версия v3.4.0, статус, строка релиза, описание сканера)

**Вспомогательный (в `temp/`, в .gitignore):**
- `temp/test_day_34_5.py` — 58 проверок

---

## Запуск (ручное тестирование)

```powershell
# 1. Запуск сканера (конфиг обязателен)
python run_scanner.py scanner/config/scanner_config.json

# 2. Тестовые файлы (в D:\Projects\dcap-system\test_files)
# 2a. Плейсхолдер НЕ должен попасть в находки
echo "password=your_password" > test_files/placeholder.env
# 2b. Реальный AWS-ключ ДОЛЖЕН быть найден
echo "aws_access_key_id = AKIAIOSFODNN7EXAMPLE" > test_files/real.env
# 2c. Файл без расширения по имени ДОЛЖЕН быть найден
echo "apiVersion: v1" > test_files/kubeconfig

# 3. Самостоятельная проверка фильтров (без запуска сканера)
python temp/test_day_34_5.py
```

Находки: `CRED_AWS_ACCESS_KEY`, `CRED_PASSWORD` (для не-плейсхолдера), `CRED_ENV_FILE`/`CRED_KUBECONFIG` (по имени файла) и т.п. Текстовый лог-отчёт — через `FindingCollector.generate_report()` (без значений секретов).

---

## Команда коммита

На ветке `feature/day_35_retention` (создаётся feature-ветка дня 34.5):

```powershell
git checkout -b feature/day_34.5_secret_scanner_integration
git add scanner/classifiers/credentials_classifier.py scanner/connectors/filesystem.py scanner/handlers/finding_collector.py scanner/src/config_loader.py scanner/src/managed_scanner.py scanner/config/scanner_config.json shared/event_schema.py AGENTS.md prompts/tz/day_34.5_secret_scanner_integration.md
git commit -m "feat: День 34.5 — Интеграция Secret Scanner в DCAP

FP-фильтры:
- Плейсхолдеры (your_*, example, changeme, password1, <PASSWORD>)
- Строки-комментарии (#, //, ;, *, --)
- Дампы (только цифры/hex/один регистр) + whitelist сигнатур (AKIA/ghp_)
- Скип директорий-образцов (_example, sample, template)

Расширение типов файлов:
- .pem, .key, .crt, .csr, .p12, .pfx, .jks, .env, .envrc
- .doc, .xls (OLE) через DocumentExtractor (catdoc/xlrd)
- Кред-файлы по имени: id_rsa, .netrc, .pgpass, kubeconfig, secrets

Префильтр:
- Один regex вместо множества проходов (пропуск чистых файлов)

Буферизованное чтение:
- Чтение по 1 МБ, лимит 200 000 символов

Лог-отчёт:
- Без значений секретов (маскирование), группировка по категориям, секция ошибок"
```

---

## Обратная связь архитектору

- **Версионирование ТЗ**: в `day_34.5_secret_scanner_integration.md` указано «Версия: v3.0.0», но проект на момент старта уже v3.3.0 (день 35 retention). Релиз этого дня проставлен как **v3.4.0** (09.09.2026). Рекомендую впредь сверять номер версии в ТЗ с реальной веткой перед выдачей.
- **Пути файлов в ТЗ** упрощены (`scanner/src/classifiers/…` и т.п.) — реальные пути в `scanner/classifiers/`, `scanner/connectors/`, `scanner/handlers/`. Дальше учитывать в ТЗ.
- **DUMP_PATTERNS из ТЗ** уточнены (см. Резюме): буквальная реализация ТЗ отбрасывала бы настоящие AWS/GitHub-ключи и SHA-хеши. Если требуется полная строгость ТЗ по дампам — можно включить дополнительные паттерны через конфиг, но по умолчанию оставлен безопасный набор.
- **Префильтр** сейчас отсекает и high-entropy-поиск для файлов без regex-совпадений (быстрее, как в утилите). Если важно искать случайные токены в любых файлах — префильтр можно ослабить, но скорость упадёт.
- **`generate_report()`** возвращает текст; при необходимости прикрутить запись в файл/лог (`logs/scan_*.log`) — вынести в отдельный хендлер или вызвать после `finish_collection()`.