# Отчёт: День 53.4n — Scanner Resume (v3.14.12)

**Версия:** v3.14.11 → **v3.14.12**
**Дата:** 25.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes
**ТЗ:** `prompts/tz/day_53_4m_scanner_resume.md` (BUG-280, BUG-283, BUG-284)

---

## Кратко

Сканер теперь сохраняет состояние по чанкам (`performance.chunk_size`, по умолчанию 100).
При остановке (Ctrl+C) задание возвращается в очередь Manager через
`POST /api/scanner/tasks/{id}/release` (resume) вместо `fail` — при следующем
получении задания сканирование продолжается с последнего завершённого чанка.
Дубли отсекаются fingerprint-дедупом в Manager. Добавлен файловый лог
(`logs/scanner.log`, ротация) и логирование восстановления связи с Manager.

---

## Изменённые файлы

- `scanner/src/state_manager.py` — новый: `ScanState` (load/save/clear/get_resume_chunk,
  атомарная запись через tmp + os.replace, проверка task_id и возраста).
- `scanner/src/managed_scanner.py` — чанк-цикл в `_scan_line_by_line`
  (discover_files/scan_files, offset/total), `_execute_task_linewise` переписан:
  по-чанковый submit + state.save, `final=` для последнего чанка,
  `release_task` вместо `fail_task` при остановке, `_request`-обёртка для
  логирования reconnect, `_serialize_chunk`, `_chunk_size`.
- `scanner/connectors/filesystem.py` — публичные `discover_files`/`scan_files`
  (сортированный обход, абсолютная нумерация прогресса).
- `scanner/connectors/s3_line_connector.py` — аналогично (resume по `start_key`).
- `manager/src/api/scanner.py` — поддержка явного `final` в query (приоритет
  над batch/total, обратная совместимость).
- `scanner/src/config_loader.py` — `LoggingConfig` + поле `AppConfig.logging`.
- `run_scanner.py` — `_setup_logging` (консоль DEBUG + файл INFO с ротацией).
- `scanner/classifiers/pii_classifier.py`, `ocr_worker.py`, `ocr_engine.py` —
  print → logger.
- `ARCHITECTURE.md`, `CHANGELOG.md`, `STATE.md`, `docs/admin-guide/06-scanner.md`.

---

## Тесты

- `tests/unit/test_scan_state_v31412.py` — 6 passed.
- `tests/unit/test_logging_v31412.py` — 2 passed.
- Регрессия: `tests/unit` — **516 passed** (107 с), включая
  `test_bug097_offline_flush` (14), `test_scanner_findings` (25),
  `test_multiprocessing_v31411` (10), `test_s3_line_connector_v31331` (21).

---

## Ручной тест (resume)

1. Поднять Manager + WebUI, зарегистрировать сканер.
2. Создать задачу на каталог `E:\Temp\dcap_perf_1000` (1000 файлов),
   `chunk_size=100` в `scanner_config.json`.
3. Запустить `python run_scanner.py scanner/config/scanner_config.json`,
   дождаться обработки ≥4 чанков (лог: `[Resume] Чанк 4/10 обработан...`).
4. Нажать Ctrl+C. Ожидается: `[Resume] Задание ... приостановлено: обработано
   чанков 4/10, находок N`, файл `scanner/state/scan_<task_id>.json` содержит
   `last_completed_chunk=3`.
5. Перезапустить сканер. Ожидается: `[Resume] Задание ...: продолжаем с чанка 5/10`,
   итоговое число находок в Manager равно baseline (598) без дублей.
6. Файл лога `logs/scanner.log` содержит строки INFO (чанки, reconnect).
7. Отключить Manager на 10 с и включить — в логе появляется
   `[Manager] Соединение восстановлено ...`.

---

## Коммит

```powershell
git add -A
git commit -m "feat: День 53.4n — scanner resume (чанки, release, файловый лог, reconnect) (v3.14.12)"
```

Доки отдельным коммитом (опционально):

```powershell
git commit -m "docs: 53.4n — ARCHITECTURE/CHANGELOG/STATE/admin-guide (v3.14.12)"
```
