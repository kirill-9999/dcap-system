📋 ТЗ — ДЕНЬ 34.5: ИНТЕГРАЦИЯ SECRET SCANNER В DCAP
Файл: prompts/tz/day_34.5_secret_scanner_integration.md
Дата: 09.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Интегрировать наработки из стендэлон-утилиты dcap-secret-scanner в основной scanner/ DCAP:

FP-фильтры — подавление ложных срабатываний (плейсхолдеры, комментарии, дампы)

Расширение типов файлов — .pem, .key, .crt, .env, .p12, .pfx, .jks, Office (.doc, .xls)

Префильтр — один regex вместо множества проходов

Буферизованное чтение — чтение по 1 МБ вместо f.read()

Детекция по имени файла — id_rsa, .pgpass, .netrc, kubeconfig, secrets*

Текстовый лог-отчёт — безопасный лог без значений секретов

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Файл	Изменение
scanner/src/classifiers/credentials_classifier.py	FP-фильтры, префильтр, детекция по имени
scanner/src/connectors/filesystem.py	Расширение типов, буферизованное чтение
scanner/src/core/orchestrator.py	Интеграция новых фильтров
scanner/src/handlers/finding_collector.py	Формат находок, лог-отчёт
scanner/src/config_loader.py	Новые параметры конфига
scanner/config/scanner_config.json	Новые параметры
shared/event_schema.py	Расширение категорий находок
🔧 ДЕТАЛЬНОЕ ТЗ
1. FP-фильтры (credentials_classifier.py)
python
# scanner/src/classifiers/credentials_classifier.py (дополнение)

# ===== ПЛЕЙСХОЛДЕРЫ =====
PLACEHOLDER_PATTERNS = [
    r'your_[a-z_]+',           # your_key, your_password
    r'example_[a-z_]+',        # example_key
    r'changeme',               # changeme
    r'<[A-Z_]+>',              # <PASSWORD>
    r'{{[A-Z_]+}}',            # {{PASSWORD}}
    r'xxx+',                   # xxx, xxxx
    r'[0-9x]{8,}',             # 12345678, xxxxxxxx
    r'NNN[_-]?[A-Z]+',         # NNN_KEY
    r'password[0-9]{1,2}',     # password1, password12
    r'admin[0-9]{1,2}',        # admin1
    r'test[_-]?[a-z0-9]+',     # test_key, test-123
    r'sample[_-]?[a-z0-9]+',   # sample_key
    r'demo[_-]?[a-z0-9]+',     # demo_key
    r'example\.com',           # example.com
    r'changeme\.com',          # changeme.com
]

# ===== КОММЕНТАРИИ =====
COMMENT_PATTERNS = [
    r'^\s*#',                  # shell/python
    r'^\s*//',                 # C/JS/Go
    r'^\s*;',                  # INI
    r'^\s*\*',                 # многострочные
    r'^\s*--',                 # SQL
    r'^\s*<!--',               # HTML
]

# ===== ДАМПЫ =====
DUMP_PATTERNS = [
    r'^\d+$',                  # только цифры
    r'^[0-9a-fA-F]+$',         # только hex
    r'^[0-9a-fA-F]{32,}$',     # MD5/SHA-like
    r'^[A-Z0-9]{16,}$',        # CAPS-only
    r'^[a-z0-9]{16,}$',        # lower-only
    r'^[A-Za-z]{16,}$',        # alpha-only
]

# ===== СКИП ДИРЕКТОРИЙ =====
SKIP_DIRS_PATTERNS = [
    r'_example/',
    r'sample/',
    r'template/',
    r'\.git/',
    r'\.hg/',
    r'\.svn/',
    r'__pycache__/',
    r'node_modules/',
    r'vendor/',
    r'dist/',
    r'build/',
]

class CredentialsClassifier:
    def __init__(self, config):
        # ... существующий код ...
        
        # Новые настройки
        self.strict_filter = config.get("strict_filter", True)
        self.min_entropy = config.get("min_entropy", 4.5)
        self.min_length = config.get("min_length", 8)
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self.no_generic = config.get("no_generic", False)
        self.require_mixed = config.get("require_mixed", False)
    
    def _is_placeholder(self, value: str) -> bool:
        """Проверка: является ли значение плейсхолдером"""
        for pattern in PLACEHOLDER_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    def _is_comment_line(self, line: str) -> bool:
        """Проверка: является ли строка комментарием"""
        for pattern in COMMENT_PATTERNS:
            if re.match(pattern, line):
                return True
        return False
    
    def _is_dump_value(self, value: str) -> bool:
        """Проверка: является ли значение дампом (только цифры/hex и т.п.)"""
        for pattern in DUMP_PATTERNS:
            if re.match(pattern, value):
                return True
        return False
    
    def _should_skip_dir(self, path: str) -> bool:
        """Проверка: нужно ли пропустить директорию"""
        for pattern in SKIP_DIRS_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False
    
    def _apply_filters(self, value: str, line: str) -> bool:
        """Применение всех FP-фильтров"""
        # 1. Плейсхолдеры
        if self._is_placeholder(value):
            return False
        
        # 2. Комментарии
        if self._is_comment_line(line):
            return False
        
        # 3. Дампы
        if self._is_dump_value(value):
            return False
        
        # 4. Минимальная длина
        if len(value) < self.min_length:
            return False
        
        # 5. Энтропия
        if self._shannon_entropy(value) < self.min_entropy:
            return False
        
        # 6. Смешанные символы (если включено)
        if self.require_mixed and not self._has_mixed_case(value):
            return False
        
        return True
2. Расширение типов файлов (filesystem.py)
python
# scanner/src/connectors/filesystem.py (дополнение)

# ===== РАСШИРЕННЫЕ ТИПЫ ФАЙЛОВ =====
TEXT_EXTENSIONS = {
    # Существующие
    '.txt', '.log', '.cfg', '.conf', '.ini', '.json', '.yaml', '.yml',
    '.toml', '.xml', '.html', '.css', '.js', '.ts', '.jsx', '.tsx',
    '.py', '.java', '.go', '.rs', '.c', '.cpp', '.h', '.hpp',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.cmd', '.bat',
    '.sql', '.php', '.rb', '.pl', '.pm', '.lua', '.r', '.swift',
    '.kt', '.scala', '.clj', '.exs', '.erl', '.hs', '.ml',
    
    # НОВЫЕ (из стендэлон-утилиты)
    '.pem', '.key', '.crt', '.csr', '.p12', '.pfx', '.jks',
    '.env', '.envrc', '.env.local', '.env.production',
    '.dockerignore', '.gitignore', '.gitattributes',
    '.npmrc', '.pypirc', '.gemrc', '.boto', '.aws/config',
    
    # Конфигурационные файлы
    'kubeconfig', '.kubeconfig',
    '.netrc', '.pgpass', '.my.cnf', '.my.ini',
    'jaas.conf',
}

# ===== ИМЕНА ФАЙЛОВ С CREDENTIALS =====
CRED_FILE_NAMES = {
    'id_rsa': 'ssh_private_key',
    'id_dsa': 'ssh_private_key',
    'id_ecdsa': 'ssh_private_key',
    'id_ed25519': 'ssh_private_key',
    '.pgpass': 'postgres_password',
    '.netrc': 'netrc_credentials',
    'kubeconfig': 'kubeconfig',
    '.kubeconfig': 'kubeconfig',
    'jaas.conf': 'jaas_credentials',
    'secrets': 'secrets_file',
    'secrets.json': 'secrets_file',
    'secret': 'secrets_file',
    '.env': 'env_file',
    '.envrc': 'env_file',
    '.npmrc': 'npmrc_credentials',
    '.pypirc': 'pypirc_credentials',
    '.gemrc': 'gemrc_credentials',
    '.boto': 'boto_credentials',
}

# ===== СКИП ДИРЕКТОРИЙ (дополнение) =====
SKIP_DIRS = {
    # Существующие
    '__pycache__', '.git', '.hg', '.svn', 'node_modules', 'vendor',
    'dist', 'build', 'target', '.idea', '.vscode',
    
    # НОВЫЕ
    '_example', 'sample', 'template', 'examples', 'samples',
    'templates', 'test_data', 'fixtures', 'mocks',
}

class FileSystemConnector:
    def __init__(self, config):
        # ... существующий код ...
        
        # Новые настройки
        self.buffer_size = config.get("buffer_size", 1024 * 1024)  # 1 MB
        self.max_file_size = config.get("max_file_size", 50 * 1024 * 1024)  # 50 MB
        self.max_text_chars = config.get("max_text_chars", 200000)
    
    def read_file_buffered(self, path: str) -> Optional[str]:
        """Буферизованное чтение файла (1 МБ)"""
        try:
            size = os.path.getsize(path)
            if size > self.max_file_size:
                return None
            
            content = ""
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    chunk = f.read(self.buffer_size)
                    if not chunk:
                        break
                    content += chunk
                    if len(content) > self.max_text_chars:
                        content = content[:self.max_text_chars]
                        break
            return content
            
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return None
    
    def should_scan_by_name(self, path: str) -> Optional[str]:
        """Проверка: является ли файл credential по имени"""
        basename = os.path.basename(path)
        for name, category in CRED_FILE_NAMES.items():
            if basename == name or basename.endswith(name):
                return category
        return None
    
    def should_skip_dir(self, path: str) -> bool:
        """Проверка: нужно ли пропустить директорию"""
        basename = os.path.basename(path)
        return basename in SKIP_DIRS or any(pattern in path for pattern in ['_example', '/sample/', '/template/'])
3. Префильтр (credentials_classifier.py)
python
# scanner/src/classifiers/credentials_classifier.py (дополнение)

class CredentialsClassifier:
    def __init__(self, config):
        # ... существующий код ...
        
        # Компиляция единого префильтра
        self._compile_prefilter()
    
    def _compile_prefilter(self):
        """Компиляция единого regex для предварительной фильтрации"""
        all_patterns = []
        for rule in self.rules:
            all_patterns.append(rule.pattern)
        
        # Объединение всех паттернов в один
        combined = '|'.join(f'({p})' for p in all_patterns)
        self.prefilter_regex = re.compile(combined, re.IGNORECASE)
    
    def prefilter(self, content: str) -> bool:
        """Быстрая проверка: есть ли хоть один паттерн в контенте"""
        return bool(self.prefilter_regex.search(content))
    
    def analyze(self, content: str, file_path: str = None) -> List[Finding]:
        """Анализ с предварительной фильтрацией"""
        # 1. Быстрая проверка (префильтр)
        if not self.prefilter(content):
            return []
        
        # 2. Детальный анализ (существующая логика)
        findings = []
        # ... существующий код ...
        
        # 3. Применение FP-фильтров
        filtered = []
        for finding in findings:
            if self._apply_filters(finding.value, finding.context):
                filtered.append(finding)
        
        return filtered
4. Текстовый лог-отчёт (finding_collector.py)
python
# scanner/src/handlers/finding_collector.py (дополнение)

class FindingCollector:
    def generate_report(self, findings: List[Finding], errors: List[str]) -> str:
        """Генерация текстового лог-отчёта без значений секретов"""
        
        lines = []
        lines.append("=" * 80)
        lines.append("DCAP SCAN REPORT")
        lines.append("=" * 80)
        lines.append(f"Total files: {self.total_files}")
        lines.append(f"Scanned files: {self.scanned_files}")
        lines.append(f"Findings: {len(findings)}")
        lines.append(f"Errors: {len(errors)}")
        lines.append("=" * 80)
        
        # Группировка по категориям
        by_category = {}
        for f in findings:
            category = f.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(f)
        
        lines.append("\n[FILES WITH FINDINGS]")
        for category, items in by_category.items():
            lines.append(f"\n{category.upper()}:")
            for item in items:
                # Без значений секретов
                lines.append(f"  {item.file_path} ({item.subcategory})")
        
        if errors:
            lines.append("\n[FAILED TO PROCESS]")
            for error in errors:
                lines.append(f"  {error}")
        
        lines.append("=" * 80)
        return "\n".join(lines)
5. Конфигурация (scanner_config.json)
json
{
    "credentials_classifier": {
        "strict_filter": true,
        "min_entropy": 4.5,
        "min_length": 8,
        "confidence_threshold": 0.7,
        "no_generic": false,
        "require_mixed": false
    },
    "filesystem": {
        "buffer_size": 1048576,
        "max_file_size": 52428800,
        "max_text_chars": 200000
    },
    "report": {
        "include_secrets": false,
        "format": "text"
    }
}
✅ КРИТЕРИИ ПРИЕМКИ
FP-фильтры
□ Плейсхолдеры (your_*, example, changeme) — не попадают в находки
□ Строки-комментарии (#, //, ;, *, --) — не попадают в находки
□ Дампы (только цифры, только hex) — не попадают в находки
□ Директории-образцы (_example/, sample/) — не сканируются
Расширение типов
□ .pem, .key, .crt, .csr, .p12, .pfx, .jks — сканируются
□ .env, .envrc, .env.local — сканируются
□ .netrc, .pgpass, kubeconfig, jaas.conf — сканируются
□ .doc, .xls (OLE) — извлекаются строки
Префильтр
□ Один regex для всех паттернов
□ Пропуск файлов без совпадений
Буферизация
□ Чтение по 1 МБ
□ Лимит 200 000 символов
Лог-отчёт
□ Без значений секретов
□ С группировкой по категориям
□ С секцией ошибок
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Тест FP-фильтров
echo "password=your_password" > test_env
# Должен быть пропущен (плейсхолдер)

# 2. Тест расширенных типов
echo "AWS_KEY=AKIA..." > test.env
# Должен быть найден

# 3. Тест префильтра
python -m scanner.src.managed_scanner --config config/scanner_config.json
# Должен работать быстрее

# 4. Тест лог-отчёта
# logs/scan_*.log — без значений секретов
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_34.5_secret_scanner_integration
git add .
git commit -m "feat: День 34.5 — Интеграция Secret Scanner в DCAP

FP-фильтры:
- Плейсхолдеры (your_*, example, changeme)
- Строки-комментарии (#, //, ;, *, --)
- Дампы (только цифры/hex)
- Скип директорий-образцов (_example/, sample/)

Расширение типов файлов:
- .pem, .key, .crt, .csr, .p12, .pfx, .jks
- .env, .envrc, .env.local
- .netrc, .pgpass, kubeconfig, jaas.conf
- .doc, .xls (OLE)

Префильтр:
- Один regex вместо множества проходов

Буферизованное чтение:
- Чтение по 1 МБ
- Лимит 200 000 символов

Лог-отчёт:
- Без значений секретов
- Группировка по категориям
- Секция ошибок"