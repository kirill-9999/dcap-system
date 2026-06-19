#!/usr/bin/env python
"""Скрипт для экспорта всех исходников DCAP v3.0 в один файл"""

import os
import sys
from pathlib import Path
from datetime import datetime
import fnmatch

# Расширения файлов, которые включаем
INCLUDE_EXTENSIONS = {
    '.py', '.proto', '.html', '.css', '.js', 
    '.txt', '.toml', '.yml', '.yaml', '.json',
    '.ps1', '.sh', '.bat', '.md'
}

# Папки для исключения
EXCLUDE_DIRS = {
    '__pycache__', '.pytest_cache', '.mypy_cache',
    'venv', 'env', '.venv', '.env',
    '.git', '.idea', '.vscode',
    'proto_gen', 'dcap',  # сгенерированные файлы
    'node_modules', 'dist', 'build',
    'logs', 'tmp', 'temp'
}

# Файлы для исключения
EXCLUDE_FILES = {
    '.gitignore', '.DS_Store', 'Thumbs.db',
    '*.db', '*.sqlite3', '*.pyc', '*.pyo',
    '*.so', '*.dll', '*.exe', '*.msi',
    '*.zip', '*.tar', '*.gz', '*.rar',
    '*.jpg', '*.png', '*.gif', '*.ico',
    '*.pdf', '*.docx', '*.xlsx'
}

# Особые файлы, которые включаем всегда (даже если в исключениях)
FORCE_INCLUDE = {
    '.gitignore'
}

def should_include_file(filepath: Path, root_dir: Path) -> bool:
    """Проверяем, нужно ли включать файл"""
    
    # Относительный путь
    rel_path = filepath.relative_to(root_dir)
    
    # Проверяем расширение
    ext = filepath.suffix.lower()
    if ext not in INCLUDE_EXTENSIONS:
        return False
    
    # Проверяем исключения
    for pattern in EXCLUDE_FILES:
        if fnmatch.fnmatch(filepath.name, pattern):
            return filepath.name in FORCE_INCLUDE
    
    return True

def should_include_dir(dirpath: Path, root_dir: Path) -> bool:
    """Проверяем, нужно ли включать директорию"""
    rel_path = dirpath.relative_to(root_dir)
    
    # Проверяем каждый компонент пути
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return False
    
    return True

def collect_files(root_dir: Path) -> list:
    """Собираем все файлы для экспорта"""
    files = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirpath = Path(dirpath)
        
        # Фильтруем директории
        dirnames[:] = [d for d in dirnames if should_include_dir(dirpath / d, root_dir)]
        
        # Фильтруем файлы
        for filename in filenames:
            filepath = dirpath / filename
            if should_include_file(filepath, root_dir):
                files.append(filepath)
    
    return sorted(files)

def format_file_content(filepath: Path, root_dir: Path) -> str:
    """Форматируем содержимое файла для экспорта"""
    rel_path = filepath.relative_to(root_dir)
    
    # Заголовок файла
    result = []
    result.append("=" * 80)
    result.append(f"ФАЙЛ: {rel_path}")
    result.append(f"ПУТЬ: {filepath}")
    result.append("=" * 80)
    result.append("")
    
    # Читаем содержимое файла
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Определяем язык для маркеров
        ext = filepath.suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.html': 'html',
            '.css': 'css',
            '.proto': 'protobuf',
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.toml': 'toml',
            '.ps1': 'powershell',
            '.sh': 'bash',
            '.bat': 'batch',
            '.md': 'markdown',
            '.txt': 'text'
        }
        lang = lang_map.get(ext, 'text')
        
        result.append(f"```{lang}")
        result.append(content)
        if not content.endswith('\n'):
            result.append("")
        result.append("```")
        result.append("")
        
    except UnicodeDecodeError:
        result.append("[БИНАРНЫЙ ФАЙЛ - НЕ ВКЛЮЧЁН]")
        result.append("")
    except Exception as e:
        result.append(f"[ОШИБКА ЧТЕНИЯ: {e}]")
        result.append("")
    
    return "\n".join(result)

def create_export(root_dir: Path, output_file: str = "dcap_sources_export.txt"):
    """Создаём экспорт всех исходников"""
    
    print(f"📁 Сканируем: {root_dir}")
    print(f"📄 Экспорт в: {output_file}")
    
    # Собираем файлы
    files = collect_files(root_dir)
    print(f"📊 Найдено файлов: {len(files)}")
    
    # Создаём экспорт
    with open(output_file, 'w', encoding='utf-8') as f:
        # Заголовок
        f.write("=" * 80 + "\n")
        f.write("DCAP DISTRIBUTED v3.0 - ЭКСПОРТ ИСХОДНИКОВ\n")
        f.write(f"ДАТА: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"КОРНЕВАЯ ПАПКА: {root_dir}\n")
        f.write(f"ВСЕГО ФАЙЛОВ: {len(files)}\n")
        f.write("=" * 80 + "\n\n")
        
        # Список файлов
        f.write("📋 СПИСОК ФАЙЛОВ:\n")
        f.write("-" * 40 + "\n")
        for i, filepath in enumerate(files, 1):
            rel_path = filepath.relative_to(root_dir)
            f.write(f"{i:4}. {rel_path}\n")
        f.write("\n" + "=" * 80 + "\n\n")
        
        # Содержимое файлов
        f.write("📄 СОДЕРЖИМОЕ ФАЙЛОВ:\n")
        f.write("=" * 80 + "\n\n")
        
        for i, filepath in enumerate(files, 1):
            print(f"  [{i}/{len(files)}] {filepath.relative_to(root_dir)}")
            
            content = format_file_content(filepath, root_dir)
            f.write(content)
            f.write("\n")
    
    print(f"\n✅ Экспорт завершён!")
    print(f"📄 Файл: {output_file}")
    print(f"📊 Размер: {os.path.getsize(output_file) / 1024:.2f} KB")
    print(f"📁 Файлов: {len(files)}")

def main():
    """Основная функция"""
    # Корневая директория проекта
    root_dir = Path(__file__).parent
    
    # Имя выходного файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"dcap_sources_{timestamp}.txt"
    
    print("""
    ╔══════════════════════════════════════════════╗
    ║   DCAP v3.0 - Экспорт исходников           ║
    ║   Создаёт один файл со всеми исходниками   ║
    ╚══════════════════════════════════════════════╝
    """)
    
    create_export(root_dir, output_file)

if __name__ == "__main__":
    main()