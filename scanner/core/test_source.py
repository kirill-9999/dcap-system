# test_source.py
from pathlib import Path

sources = ["E:\\projects", "z:\\install"]

for source in sources:
    print(f"\n{'='*60}")
    print(f"Проверка: {source}")
    print(f"{'='*60}")
    
    path = Path(source)
    print(f"Существует: {path.exists()}")
    
    if path.exists():
        print(f"Это директория: {path.is_dir()}")
        try:
            # Пытаемся получить список файлов (первые 5)
            files = list(path.glob("*"))[:5]
            print(f"Найдено файлов/папок: {len(list(path.glob('*')))}")
            for f in files:
                print(f"  - {f.name}")
        except PermissionError as e:
            print(f"Ошибка доступа: {e}")
        except Exception as e:
            print(f"Ошибка: {e}")
    else:
        print(f"❌ Путь НЕ СУЩЕСТВУЕТ!")