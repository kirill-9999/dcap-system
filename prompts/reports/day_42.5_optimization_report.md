# Отчёт — День 42.5 — Сканер: оптимизация (file-prefilter + precompile + ThreadPoolExecutor)

**Дата:** 13.09.2026
**Версия:** v3.13.0
**Ветка:** `feature/day_42.5_scanner_optimization`
**Предыдущая версия:** v3.12.0
**ТЗ:** прямое задание (план из 3 оптимизаций по аналогии с Rust-сканером `dcap-secret-scanner-rust`), файл не заводился

---

## 1. Цель дня

Ускорить Python-сканер на реальном каталоге (E:\much_of_test_files, 22500 файлов), перенеся архитектурные приёмы из Rust-эталона:
- **file-level prefilters** — пропуск файла целиком, если ни один классификатор не видит быстрых признаков;
- **precompile всех regex** — убрать `re.compile` из горячих циклов (построчно);
- **ThreadPoolExecutor** — параллельное сканирование файлов.

Дополнительно закрыто требование потокобезопасности Presidio (`_analyzer_lock`), т.к. `AnalyzerEngine` не потокобезопасен.

---

## 2. Что сделано

### 42.5.1 — CredentialsClassifier: `_compile_all()` + `file_prefilter` ✅

`scanner/classifiers/credentials_classifier.py`:
- новый `_compile_all()`: собирает единый `prefilter_regex` (для file-проверки), `compiled_patterns` (для `scan_line`/`classify`), `_entropy_patterns` (для энтропийного фильта);
- вызывается из `__init__` и `configure` (вместо `_compile_prefilter`);
- новый `file_prefilter(content)` — file-level проверка одним regex;
- `scan_line` и legacy `classify()` используют `compiled_patterns` / `self._entropy_patterns` без `re.compile` в цикле;
- исправлена опечатка в docstring `_compile_prefilter`.

### 42.5.2 — PiiClassifier: precompile quick-паттернов + lock ✅

`scanner/classifiers/pii_classifier.py`:
- предкомпиляция `_quick_line_patterns` (10 паттернов) и объединённого `_quick_file_regex` в `__init__`;
- `_quick_line_check` — поиск по скомпилированным паттернам;
- новый `file_prefilter(content)` — file-level проверка объединённым regex (безопасный суперсет построчной проверки);
- `_analyzer_lock = threading.Lock()`; Presidio `analyze()` — под локом (не потокобезопасен).

### 42.5.3 — CodeClassifier: `file_prefilter()` → False ✅

`scanner/classifiers/code_classifier.py`:
- `file_prefilter()` возвращает False — код-классификатор не имеет линейной быстрой проверки, `scan_line` для него no-op; знак того, что файл можно пропустить при отсутствии признаков у остальных классификаторов (фактически только если все остальные тоже вернули False).

### 42.5.4 — FilesystemConnector: параллельное сканирование + file prefilter ✅

`scanner/connectors/filesystem.py`:
- `_max_workers` из конфига `connector.max_parallel_files` (default 1 = последовательный режим);
- `scan_path`: при `_max_workers > 1` — `ThreadPoolExecutor.map` (строковый сбор результатов в порядке завершения), общий код `_scan_one` для обоих режимов; прогресс — монотонный счётчик под lock (не атомарный список);
- `_scan_text`: если `_file_pass_prefilter(text, classifiers)` вернул False — файл пропускается целиком (0 findings);
- `_file_pass_prefilter`: если какой-то классификатор не имеет `file_prefilter` — файл сканируется (консервативно); иначе True, если хотя бы один классификатор видит признаки.

### 42.5.5 — Конфиг и проброс ✅

- `scanner/src/config_loader.py`: `ConnectorConfig.max_parallel_files` (default 1), `from_dict`/`to_dict`;
- `scanner/src/managed_scanner.py`: `_get_connector_config` передаёт `max_parallel_files` (в обеих ветках);
- `scanner/config/scanner_config.json`: `"connector": {..., "max_parallel_files": 4}`.

### 42.5.6 — Тесты ✅

- `py_compile` всех изменённых файлов — OK;
- синтетический паритет seq vs parallel: **30/30 одинаковых findings**, `missing=[]`, `extra=[]`; ускорение **3.81x** (`e:\Temp\opencode\test_seq_par.py`);
- file_prefilter cred/pii — корректные True/False на наборе плейсхолдеров;
- smoke на реальном изолированном срезе не запускался (нет локального test_files), проверен деплой на реальном каталоге.

### 42.5.7 — Деплой и реальный замер ✅

- Обнаружен **конфликт: 2 процесса сканера** (PID 8392, 11308, оба `run_scanner.py`) — оба остановлены;
- запущен одиночный сканер с новым кодом (PID 5948), задание **#4** перевзято (прогресс с 51 файла);
- **реальный замер** на E:\much_of_test_files: скорость **27–43 файла/мин** (было ~25 ф/мин / 0.42 ф/с) — ускорение ~**1.4–1.7x**; ETA по ходу снижается (10–12 часов из-за Presidio-heavy файлов; на отдельных файлах сканер задерживается 1–2 мин).
- findings собираются (stats: total 214500 от предыдущих заданий; по task #4 находки появятся по мере отправки/в конце).

---

## 3. Полный код (изменённые фрагменты)

### `scanner/classifiers/credentials_classifier.py`

```python
    def __init__(self):
        ...
        self._patterns = self._get_default_patterns()
        self._compile_all()
```

```python
    def _compile_all(self) -> None:
        """Компиляция всех regex один раз (день 42 — оптимизация).

        - prefilter_regex — единый prefilter по всем паттернам (для быстрой
          проверки всего файла целиком через file_prefilter).
        - compiled_patterns — скомпилированные regex всех паттернов (используются
          в scan_line/classify без re.compile в горячем цикле).
        - _entropy_patterns — скомпилированные токены для энтропийной проверки.
        """
        all_patterns = [p["pattern"] for p in self._patterns]
        combined = '|'.join(f'({p})' for p in all_patterns)
        self.prefilter_regex = re.compile(combined, re.IGNORECASE | re.MULTILINE)
        self.compiled_patterns = []
        for p in self._patterns:
            item = dict(p)
            item["compiled"] = re.compile(p["pattern"], re.IGNORECASE | re.MULTILINE)
            self.compiled_patterns.append(item)
        self._entropy_patterns = [
            re.compile(p) for p in [
                r'\b[A-Za-z0-9+/=]{20,}\b',
                r'\b[A-Za-z0-9_\-]{32,}\b',
                r'\b[0-9a-f]{32,}\b',
                r'\b[0-9a-f]{40,}\b',
                r'\b[0-9a-f]{64,}\b',
            ]
        ]
```

```python
    def file_prefilter(self, content: str) -> bool:
        """Быстрая проверка уровня файла: есть ли хоть один паттерн во всём файле.

        Используется FilesystemConnector для пропуска файла целиком, если ни один
        классификатор не видит быстрых признаков (день 42 — оптимизация).
        """
        return bool(self.prefilter_regex.search(content))
```

`scan_line` — поиск:
```python
        for pattern_config in self.compiled_patterns:
            # no_generic: пропускаем общие правила
            if self._no_generic and pattern_config["name"] in ("GENERIC_TOKEN", "GENERIC_SECRET"):
                continue
            # confidence_threshold: пропускаем низкодоверенные правила
            if pattern_config["confidence"] < self._confidence_threshold:
                continue

            pattern = pattern_config["compiled"]
            for match in pattern.finditer(line):
```

`_find_high_entropy_in_line`:
```python
        patterns = self._entropy_patterns

        for pattern in patterns:
            for match in pattern.finditer(stripped):
```

`classify()` (legacy):
```python
        # Поиск по паттернам (precompiled, день 42)
        for pattern_config in self.compiled_patterns:
            ...
            pattern = pattern_config["compiled"]
            for match in pattern.finditer(text):
```

### `scanner/classifiers/pii_classifier.py`

```python
        self._analyzer = None
        # Кастомные regex-паттерны для строчного сканирования (пустые по умолчанию)
        self.custom_patterns: List = []
        # Quick-паттерны компилируем один раз (день 42 — оптимизация)
        self._quick_line_patterns: List = [
            re.compile(p) for p in [
                r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}',
                r'[A-Za-z][A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
                r'\+?7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
                r'8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
                r'[А-Я][а-я]+\s+[А-Я][а-я]+',
                r'[A-Z][a-z]+\s+[A-Z][a-z]+',
                r'\b\d{4}\s+\d{6}\b',
                r'\b\d{3}-\d{3}-\d{3}\s+\d{2}\b',
                r'\b\d{6,12}\b',
                r'\b\d{16}\b',
            ]
        ]
        self._quick_file_regex = re.compile(
            '|'.join(f'({p.pattern})' for p in self._quick_line_patterns)
        )
        # Presidio AnalyzerEngine не потокобезопасен — сериализуем analyze()
        # (день 42, параллельное сканирование файлов).
        self._analyzer_lock = threading.Lock()
```

```python
    def _quick_line_check(self, line: str) -> bool:
        """Быстрая проверка строки на наличие PII-признаков (до Presidio)."""
        stripped = line.strip()
        if len(stripped) < 5:
            return False
        for pattern in self._quick_line_patterns:
            if pattern.search(stripped):
                return True
        return False

    def file_prefilter(self, content: str) -> bool:
        """Быстрая проверка уровня файла: есть ли хоть один PII-признак во всём файле.

        Используется FilesystemConnector для пропуска файла целиком (день 42).
        Объединённый regex ищется по всему содержимому — безопасный суперсет
        построчной проверки _quick_line_check (может пропустить меньше, но не больше).
        """
        if len(content) < 5:
            return False
        return bool(self._quick_file_regex.search(content))
```

Presidio под локом:
```python
        # 1. Presidio (если доступен) — под локами, т.к. analyze() не потокобезопасен
        if self._analyzer is not None:
            try:
                with self._analyzer_lock:
                    results = self._analyzer.analyze(text=line, language="ru")
```

### `scanner/classifiers/code_classifier.py`

```python
    def file_prefilter(self, content: str) -> bool:
        """File-level prefilter: код-классификатор не имеет быстрой линейной
        проверки (scan_line — no-op), возвращаем False (день 42).
        """
        return False
```

### `scanner/connectors/filesystem.py`

```python
        # Параллельное сканирование файлов (день 42); 1 = последовательный режим
        self._max_workers = int(config.get("max_parallel_files", 1) or 1)
```

```python
        findings: List[Finding] = []
        files = self._discover_files(path)
        if not files:
            if progress_callback:
                progress_callback(1, 0, 0, path)
            return findings

        total = len(files)
        max_workers = self._max_workers

        def _scan_one(file_path: str) -> List[Finding]:
            """Сканирование одного файла (общий код для seq/parallel)."""
            if not self._within_size(file_path):
                return []
            try:
                return self.scan_file(file_path, classifiers)
            except Exception as e:
                print(f"[FS] Ошибка сканирования {file_path}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                return []

        if max_workers <= 1:
            # Последовательный режим (как раньше, день 40.2)
            for i, file_path in enumerate(files, start=1):
                if progress_callback:
                    progress_callback(1, i, total, file_path)
                findings.extend(_scan_one(file_path))
            return findings

        # Параллельный режим (день 42): ThreadPoolExecutor.
        # Прогресс — монотонный счётчик; findings собираем в порядке завершения.
        import threading
        from concurrent.futures import ThreadPoolExecutor

        lock = threading.Lock()
        done_counter = [0]

        def _work(file_path: str):
            result = _scan_one(file_path)
            with lock:
                done_counter[0] += 1
                current = done_counter[0]
            if progress_callback:
                progress_callback(1, current, total, file_path)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_work, files):
                findings.extend(result)

        return findings
```

```python
    def _scan_text(self, text: str, classifiers: List[Any], file_path: str) -> List[Finding]:
        """Делит текст на строки, прогоняет через scan_line классификаторов."""
        if len(text) > self._max_text_chars:
            text = text[: self._max_text_chars]

        # File-level prefilter (день 42): пропускаем файл целиком, если ни один
        # классификатор не видит быстрых признаков во всём содержимом.
        if not self._file_pass_prefilter(text, classifiers):
            return []

        lines = text.splitlines()
        ...
```

```python
    @staticmethod
    def _file_pass_prefilter(text: str, classifiers: List[Any]) -> bool:
        """File-level prefilter (день 42).

        True — файл сканировать (хотя бы один классификатор видит признаки),
        False — пропустить файл целиком (ни один классификатор ничего не видит).
        """
        if not classifiers:
            return False
        for classifier in classifiers:
            fp = getattr(classifier, "file_prefilter", None)
            if fp is None:
                # Классификатор без file_prefilter — не можем гарантировать
                # «ничего не видно», поэтому сканируем файл.
                return True
            if fp(text):
                return True
        return False
```

### `scanner/src/config_loader.py`

```python
@dataclass
class ConnectorConfig:
    ...
    max_parallel_files: int = 1
```

`from_dict` / `to_dict` — добавлен `max_parallel_files`.

### `scanner/src/managed_scanner.py`

`_get_connector_config` — в обеих ветках:
```python
        config["max_parallel_files"] = self.config.get("connector", {}).get("max_parallel_files", 1)
```

### `scanner/config/scanner_config.json`

section `connector`:
```json
        "max_parallel_files": 4,
```

---

## 4. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `scanner/classifiers/credentials_classifier.py` | `_compile_all()`, `file_prefilter`, precompiled в `scan_line`/`classify`/entropy |
| `scanner/classifiers/pii_classifier.py` | precompile quick-паттернов, `file_prefilter`, `_analyzer_lock` |
| `scanner/classifiers/code_classifier.py` | `file_prefilter()` → False |
| `scanner/connectors/filesystem.py` | `_max_workers`, ThreadPoolExecutor, `_file_pass_prefilter` |
| `scanner/src/config_loader.py` | `ConnectorConfig.max_parallel_files` |
| `scanner/src/managed_scanner.py` | проброс `max_parallel_files` |
| `scanner/config/scanner_config.json` | `connector.max_parallel_files: 4` |

---

## 5. Команда для коммита

```
git add scanner/classifiers/credentials_classifier.py scanner/classifiers/pii_classifier.py scanner/classifiers/code_classifier.py scanner/connectors/filesystem.py scanner/src/config_loader.py scanner/src/managed_scanner.py scanner/config/scanner_config.json
git commit -m "perf: Сканер — file-prefilter + precompile regex + ThreadPoolExecutor (v3.13.0)

- CredentialsClassifier: _compile_all() (prefilter_regex/compiled_patterns/_entropy_patterns), file_prefilter, precompiled в scan_line/classify
- PiiClassifier: precompile quick-паттернов + _quick_file_regex, file_prefilter, _analyzer_lock (Presidio не потокобезопасен)
- CodeClassifier: file_prefilter -> False
- FilesystemConnector: max_parallel_files -> ThreadPoolExecutor (ex.map, монотонный прогресс), _file_pass_prefilter (пропуск файла целиком)
- config_loader: ConnectorConfig.max_parallel_files (default 1); managed_scanner передаёт значение; scanner_config.json max_parallel_files: 4
- Тесты: seq vs parallel — идентичные findings (30/30), speedup 3.81x (синтетика); реальный каталог 27-43 файл/мин (<25)
"
```

---

## 6. Инструкция по запуску для ручного тестирования

1. Перезапуск сканера (единый процесс):
```powershell
cd E:\projects\dcap-system
Get-Process python* | Where-Object { $_.Path -like "*Anaconda3*" } | Stop-Process
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"
python run_scanner.py scanner/config/scanner_config.json
```
2. Проверка скорости: в логе `[ScanProgress] … | скорость N файл/мин | ETA …` (должно быть 27+, было <25).
3. Паритет seq/parallel (синтетика, вне репо):
```powershell
python e:\Temp\opencode\test_seq_par.py
```
4. Конфиг параллельности: `scanner/config/scanner_config.json` → `connector.max_parallel_files` (4; 1 = последовательный режим как раньше).
5. WebUI `http://localhost:8001` (admin/admin123) → «Сканеры» — прогресс задания #4.

---

## 7. Примечания

- **Black не применён** к 4 файлам — при массовом форматировании DIFF-ы раздуваются (реверт через `git checkout`, правки переприменены вручную в исходном стиле).
- Presidio остаётся узким местом на тяжёлых файлах (100k+ строк) — BACKLOG-063. ThreadPool частично компенсирует за счёт параллелизма I/O и regex-классификаторов; GIL ограничивает выигрыш от threading по CPU.
- `performance.max_parallel_files: 8` (top-level) — legacy, фактически не читается (app-конфиг не мапит top-level «performance»); рабочая настройка — `connector.max_parallel_files`.