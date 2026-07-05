# run_webui.py
#!/usr/bin/env python
"""
Запуск WebUI для DCAP Distributed v3.0
"""

import sys
import os

# Добавляем корень проекта в PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import uvicorn

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     🚀 DCAP Distributed v3.0 - WebUI                    ║
    ║     http://localhost:8001                              ║
    ║     Для остановки: Ctrl+C                             ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "webui.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )