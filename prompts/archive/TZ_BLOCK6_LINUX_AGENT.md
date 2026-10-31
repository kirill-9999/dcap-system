📋 ТЗ — БЛОК 6.2: LINUX-АГЕНТ В WSL 2
Файл: prompts/tz/TZ_BLOCK6_LINUX_AGENT.md
Дата: 03.10.2026
Версия: v3.13.28
Статус: ✏️ Готово к разработке
Оценка: ~40 мин
Приоритет: 🟡 важно (BACKLOG-078, BACKLOG-080)
Связано: day_23_linux_agent_inotify.md (исходное ТЗ Linux-агента)

🎯 ЦЕЛЬ
Развернуть Linux-агент аудита в WSL 2 (Ubuntu 22.04), настроить systemd-сервис,
проверить сквозной поток (inotify → агент → Manager → audit_logs).

📌 ПРЕДУСЛОВИЯ
- ✅ WSL 2 установлен, Ubuntu 22.04.5 LTS (Jammy)
- ✅ systemd работает (State: running)
- ✅ Python 3.10.12, git, curl, wget
- ✅ Manager доступен из WSL: http://localhost:8000 → HTTP 200
- ✅ /mnt/e/projects/dcap-system доступен
- ❌ python3-pip, python3-venv, inotify-tools, jq, unzip НЕ установлены
- ❌ audit-agent-linux НЕ развёрнут в ~/dcap
- ❌ systemd-сервис НЕ установлен

📁 ФАЙЛЫ
Проект (в Windows): E:\projects\dcap-system\audit-agent-linux\
- main.py
- collector.py      — pyinotify
- buffer.py         — SQLite
- sender.py
- heartbeat.py
- config.json
- requirements.txt  — requests, pyinotify
- start.sh / stop.sh (в WSL не применимы — используем systemd)
- README.md

В WSL развернём в: ~/dcap/audit-agent-linux/

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-089 — Установка пакетов в WSL

В окне Ubuntu:
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev inotify-tools build-essential unzip jq
Проверка:

bash
python3 --version       # 3.10.12
pip3 --version
inotifywait --version   # 3.22.x
jq --version
TASK-090 — Развёртывание агента

bash
# Создать рабочую директорию
mkdir -p ~/dcap
cd ~/dcap

# Скопировать агент из проекта
cp -r /mnt/e/projects/dcap-system/audit-agent-linux ~/dcap/

# Перейти
cd ~/dcap/audit-agent-linux
ls -la
TASK-091 — Виртуальное окружение

bash
cd ~/dcap/audit-agent-linux
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Установить зависимости
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
Проверка:

bash
python3 -c "import pyinotify; print('pyinotify OK')"
python3 -c "import requests; print('requests OK')"
TASK-092 — Настройка config.json

bash
cat config.json
Скорее всего, требуется обновить:

manager_url: http://localhost:8000 (из WSL работает)

agent_name: linux-agent-wsl-01

hostname: DESKTOP-9TI677N или linux-wsl

watch_paths: например, /home/<user>/dcap-test/ (директория в WSL, не /mnt/e/)

log_file: logs/audit_agent.log

⚠️ ВАЖНО: inotify НЕ работает на /mnt/e/ (Windows-диск в WSL). Только на Linux-ФС внутри WSL (~/).

Создать тестовую директорию:

bash
mkdir -p ~/dcap-test
echo "test file" > ~/dcap-test/hello.txt
TASK-093 — Ручной запуск (первая проверка)

bash
cd ~/dcap/audit-agent-linux
source venv/bin/activate
python3 main.py 2>&1 | tee /tmp/agent-manual.log
Ожидание в консоли:

[INFO] Запуск: linux-agent-wsl-01

[INFO] Зарегистрирован, ID: N

[INFO] Мониторинг: ['/home/.../dcap-test']

[INFO] Событие: read/write ...

Оставить открытым.

Создать событие (второе окно Ubuntu):

bash
echo "test 1" > ~/dcap-test/file1.txt
cat ~/dcap-test/file1.txt
rm ~/dcap-test/file1.txt
Проверить в Manager (PowerShell):

powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

Invoke-RestMethod -Method GET http://127.0.0.1:8000/api/audit/agents -Headers $headers |
    ConvertTo-Json -Depth 5 | Select-String "linux-agent-wsl-01" -Context 2,10
Ожидание: агент linux-agent-wsl-01 в списке.

Остановить агент (Ctrl+C в первом окне).

TASK-094 — systemd-сервис

Создать unit:

bash
sudo tee /etc/systemd/system/dcap-linux-agent.service > /dev/null << 'EOF'
[Unit]
Description=DCAP Linux Audit Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ser
WorkingDirectory=/home/ser/dcap/audit-agent-linux
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/ser/dcap/audit-agent-linux/venv/bin/python3 /home/ser/dcap/audit-agent-linux/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
⚠️ Замените User=ser и WorkingDirectory на актуальные.

Запустить:

bash
sudo systemctl daemon-reload
sudo systemctl enable dcap-linux-agent
sudo systemctl start dcap-linux-agent
sudo systemctl status dcap-linux-agent
Ожидание: Active: active (running).

Логи:

bash
sudo journalctl -u dcap-linux-agent -f
TASK-095 — Финальный тест: событие через службу

bash
# В WSL
echo "final" > ~/dcap-test/file2.txt
cat ~/dcap-test/file2.txt
rm ~/dcap-test/file2.txt

# Подождать 10 сек
sleep 10
Проверить в Manager:

powershell
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=linux_agent&limit=10" -Headers $headers |
    ConvertTo-Json -Depth 5
Ожидание: события от linux_agent, file_path=/home/.../dcap-test/file2.txt.

Проверка в БД:

powershell
$sql = @'
SELECT id, created_at, event_type, "user", file_path, source_host
FROM audit_logs
WHERE event_source = 'linux_agent'
ORDER BY created_at DESC
LIMIT 10;
'@
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
TASK-096 — Метрики (Prometheus :9102)

Если агент поднимает метрики на :9102:

bash
curl -s http://localhost:9102/metrics | head -20
Проверка из WSL:

bash
curl -s -o /dev/null -w "Metrics → HTTP %{http_code}\n" http://localhost:9102/metrics
🧪 КРИТЕРИИ ПРИЁМКИ
□ Все пакеты установлены (pip, inotify-tools, jq)
□ Агент развёрнут в ~/dcap/audit-agent-linux
□ venv создан, зависимости установлены
□ config.json настроен (manager_url=http://localhost:8000, watch_paths=~/dcap-test)
□ Ручной запуск работает, события отправляются
□ systemd-сервис установлен и запущен
□ systemctl status dcap-linux-agent → active (running)
□ В audit_logs Manager появились события от linux_agent
□ Метрики на :9102 (если поддерживается)
□ Сервис запускается автоматически при старте WSL

📊 LIVE-ПРОВЕРКА

bash
# Проверка systemd
sudo systemctl status dcap-linux-agent

# Тест события
echo "test" > ~/dcap-test/live.txt
sleep 10

# Проверка в Manager (PowerShell)
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=linux_agent&limit=5" -Headers $headers
⚠️ ОСОБЕННОСТИ WSL 2

inotify НЕ работает на /mnt/e/ — только на Linux-ФС внутри WSL (~/).

Если сервис не стартует: sudo journalctl -u dcap-linux-agent -l --no-pager.

Для graceful shutdown — Ctrl+C в консоли или systemctl stop.

Если systemd не запущен: проверить /etc/wsl.conf (systemd=true).

📋 ОТКРЫТЫЕ ВОПРОСЫ

Ключи Findings (FINDINGS_*) нужны ли Linux-агенту? → Нет, аудит-события не шифруются.

mTLS для агента? → Пока relaxed, mTLS strict в v3.1.0.

Буфер SQLite — путь по умолчанию? → buffer/buffer.db (относительно агента).

⚠️ ЧТО НЕ ДЕЛАЕМ

Не настраиваем mTLS strict (v3.1.0).

Не тестируем нагрузку.

Не настраиваем Prometheus scrape (отдельная задача).

Автор ТЗ: архитектор
Дата: 03.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: Linux-агент работает в WSL как systemd-сервис, события идут в Manager