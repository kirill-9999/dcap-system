# РђРіРµРЅС‚ Р°СѓРґРёС‚Р° DCAP

Р›РµРіРєРёР№ Р°РіРµРЅС‚ РґР»СЏ СЃР±РѕСЂР° СЃРѕР±С‹С‚РёР№ С„Р°Р№Р»РѕРІРѕР№ СЃРёСЃС‚РµРјС‹ Windows: С‡РёС‚Р°РµС‚ Security Log С‡РµСЂРµР·
`wevtutil`, Р±СѓС„РµСЂРёР·РёСЂСѓРµС‚ СЃРѕР±С‹С‚РёСЏ Р»РѕРєР°Р»СЊРЅРѕ (SQLite) Рё РѕС‚РїСЂР°РІР»СЏРµС‚ РёС… РІ Manager Р±Р°С‚С‡Р°РјРё.
Р‘РµР· С‚СЏР¶РµР»С‹С… Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№ (Tesseract, spaCy, Presidio) вЂ” С‚РѕР»СЊРєРѕ Python + requests.

## РЎС‚СЂСѓРєС‚СѓСЂР°

```
audit-agent-windows/
в”њв”Ђв”Ђ main.py                 # РўРѕС‡РєР° РІС…РѕРґР°, РѕСЃРЅРѕРІРЅРѕР№ С†РёРєР»
в”њв”Ђв”Ђ config.json             # РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ (РІРєР»СЋС‡Р°СЏ СЃРµРєС†РёСЋ service)
в”њв”Ђв”Ђ collector.py            # WindowsAuditCollector вЂ” С‡С‚РµРЅРёРµ Security Log (wevtutil)
в”њв”Ђв”Ђ buffer.py               # BufferManager вЂ” Р»РѕРєР°Р»СЊРЅРѕРµ С…СЂР°РЅРµРЅРёРµ СЃРѕР±С‹С‚РёР№ (SQLite)
в”њв”Ђв”Ђ sender.py               # Sender вЂ” РѕС‚РїСЂР°РІРєР° СЃРѕР±С‹С‚РёР№ Рё heartbeat РІ Manager
в”њв”Ђв”Ђ service.py              # РћР±РµСЂС‚РєР° Windows-СЃР»СѓР¶Р±С‹ (pywin32)
в”њв”Ђв”Ђ install_service.bat     # РЈСЃС‚Р°РЅРѕРІРєР° СЃР»СѓР¶Р±С‹
в”њв”Ђв”Ђ uninstall_service.bat   # РЈРґР°Р»РµРЅРёРµ СЃР»СѓР¶Р±С‹
в”њв”Ђв”Ђ start_service.bat       # Р—Р°РїСѓСЃРє СЃР»СѓР¶Р±С‹
в”њв”Ђв”Ђ stop_service.bat        # РћСЃС‚Р°РЅРѕРІРєР° СЃР»СѓР¶Р±С‹
в”њв”Ђв”Ђ restart_service.bat     # РџРµСЂРµР·Р°РїСѓСЃРє СЃР»СѓР¶Р±С‹
в”њв”Ђв”Ђ data/                   # Runtime: state.json + buffer/ (СЃРѕР·РґР°СЋС‚СЃСЏ РїСЂРё Р·Р°РїСѓСЃРєРµ)
в”њв”Ђв”Ђ logs/                   # РџР°РїРєР° Р»РѕРіРѕРІ (СЃРѕР·РґР°РµС‚СЃСЏ СЃР»СѓР¶Р±РѕР№)
в””в”Ђв”Ђ requirements.txt        # requests, pywin32
```

## РЈСЃС‚Р°РЅРѕРІРєР°

```powershell
pip install -r requirements.txt
```

## РќР°СЃС‚СЂРѕР№РєР°

РћС‚СЂРµРґР°РєС‚РёСЂСѓР№С‚Рµ `config.json`:

| РџРѕР»Рµ | РћРїРёСЃР°РЅРёРµ | РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ |
|------|----------|--------------|
| `manager_url` | URL Manager'Р° | `http://localhost:8000` |
| `agent_name` | РЈРЅРёРєР°Р»СЊРЅРѕРµ РёРјСЏ Р°РіРµРЅС‚Р° (РґР»СЏ СЂРµРіРёСЃС‚СЂР°С†РёРё) | `audit-agent-01` |
| `hostname` | РРјСЏ С…РѕСЃС‚Р°, РєРѕС‚РѕСЂРѕРµ СѓРІРёРґСЏС‚ РІ Manager | `SERVER01` |
| `read_interval` | РЎРµРєСѓРЅРґ РјРµР¶РґСѓ С‡С‚РµРЅРёРµРј Security Log | 60 |
| `batch_size` | РЎРєРѕР»СЊРєРѕ СЃРѕР±С‹С‚РёР№ РѕС‚РїСЂР°РІР»СЏС‚СЊ Р·Р° СЂР°Р· | 100 |
| `buffer_size` | РњР°РєСЃРёРјСѓРј РЅРµРѕС‚РїСЂР°РІР»РµРЅРЅС‹С… СЃРѕР±С‹С‚РёР№ РІ Р±СѓС„РµСЂРµ | 10000 |
| `heartbeat_interval` | РЎРµРєСѓРЅРґ РјРµР¶РґСѓ heartbeat | 30 |
| `event_filters` | Event ID РґР»СЏ СЃР±РѕСЂР° | `[4656, 4660, 4663, 4670, 5140, 5145]` |
| `paths` | РљР°РєРёРµ РїР°РїРєРё Р°СѓРґРёСЂРѕРІР°С‚СЊ (SACL) | `D:\test_audit` |
| `log_level` | РЈСЂРѕРІРµРЅСЊ Р»РѕРіР° | `INFO` |
| `service.*` | РџР°СЂР°РјРµС‚СЂС‹ Windows-СЃР»СѓР¶Р±С‹ (СЃРј. РЅРёР¶Рµ) | СЃРј. config.json |

## РЈСЃС‚Р°РЅРѕРІРєР° РєР°Рє СЃР»СѓР¶Р±Р° Windows

### РўСЂРµР±РѕРІР°РЅРёСЏ
- Python 3.8+
- pywin32: `pip install pywin32`

### РЈСЃС‚Р°РЅРѕРІРєР°

```powershell
cd audit-agent-windows
pip install -r requirements.txt
python service.py install
python service.py start
```

### РЈРїСЂР°РІР»РµРЅРёРµ

| РљРѕРјР°РЅРґР° | РћРїРёСЃР°РЅРёРµ |
|---------|----------|
| `python service.py start` | Р—Р°РїСѓСЃРє СЃР»СѓР¶Р±С‹ |
| `python service.py stop` | РћСЃС‚Р°РЅРѕРІРєР° СЃР»СѓР¶Р±С‹ |
| `python service.py restart` | РџРµСЂРµР·Р°РїСѓСЃРє СЃР»СѓР¶Р±С‹ |
| `python service.py remove` | РЈРґР°Р»РµРЅРёРµ СЃР»СѓР¶Р±С‹ |

РўР°РєР¶Рµ РґРѕСЃС‚СѓРїРЅС‹ Р±Р°С‚-С„Р°Р№Р»С‹: `install_service.bat`, `start_service.bat`, `stop_service.bat`,
`restart_service.bat`, `uninstall_service.bat`.

### РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ

Р›РѕРіРё РїРёС€СѓС‚СЃСЏ РІ `logs/audit_agent.log`. РўР°РєР¶Рµ РјРѕР¶РЅРѕ РїСЂРѕСЃРјРѕС‚СЂРµС‚СЊ РІ Windows Event Viewer:
- РћС‚РєСЂС‹С‚СЊ Event Viewer
- Windows Logs в†’ Application
- РСЃРєР°С‚СЊ СЃРѕР±С‹С‚РёСЏ РѕС‚ РёСЃС‚РѕС‡РЅРёРєР° DCAPAuditAgent

### РџР°СЂР°РјРµС‚СЂС‹ СЃР»СѓР¶Р±С‹ (config.json)

| РџРѕР»Рµ | РћРїРёСЃР°РЅРёРµ |
|------|----------|
| `service.display_name` | РРјСЏ СЃР»СѓР¶Р±С‹ РІ СЃРёСЃС‚РµРјРµ |
| `service.description` | РћРїРёСЃР°РЅРёРµ СЃР»СѓР¶Р±С‹ |
| `service.log_file` | РџСѓС‚СЊ Рє С„Р°Р№Р»Сѓ Р»РѕРіР° (РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РїР°РїРєРё Р°РіРµРЅС‚Р°) |
| `service.max_log_size_mb` | РњР°РєСЃРёРјР°Р»СЊРЅС‹Р№ СЂР°Р·РјРµСЂ Р»РѕРіР° (Р·Р°РіРѕС‚РѕРІРєР° РїРѕРґ СЂРѕС‚Р°С†РёСЋ) |
| `service.restart_on_failure` | РђРІС‚РѕРїРµСЂРµР·Р°РїСѓСЃРє Р°РіРµРЅС‚Р° РїСЂРё СЃР±РѕРµ |
| `service.restart_interval_sec` | РџР°СѓР·Р° РїРµСЂРµРґ РїРµСЂРµР·Р°РїСѓСЃРєРѕРј, СЃРµРє |

### РЈРґР°Р»РµРЅРёРµ

```powershell
python service.py stop
python service.py remove
```

## РќР°СЃС‚СЂРѕР№РєР° Р°СѓРґРёС‚Р° Windows (РѕРґРёРЅ СЂР°Р·, РѕС‚ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°)

```powershell
# 1. Р’РєР»СЋС‡РёС‚СЊ РїРѕР»РёС‚РёРєСѓ Р°СѓРґРёС‚Р° "File System" (GUID СЂР°Р±РѕС‚Р°РµС‚ РЅР° Р»СЋР±РѕР№ Р»РѕРєР°Р»Рё)
auditpol /set /subcategory:{0CCE921D-69AE-11D9-BED3-505054503030} /success:enable /failure:enable

# 2. РќР°Р·РЅР°С‡РёС‚СЊ SACL РЅР° Р°СѓРґРёСЂСѓРµРјСѓСЋ РїР°РїРєСѓ (РЅР°РїСЂРёРјРµСЂ D:\test_audit)
icacls "D:\test_audit" /grant *S-1-1-0:(OI)(CI)(RX,W,DE,DC,WDAC,WO,WA) /T
```

> Р§С‚РµРЅРёРµ Security Log С‚СЂРµР±СѓРµС‚ РїСЂР°РІ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°. Р•СЃР»Рё Р·Р°РїСѓСЃС‚РёС‚СЊ Р°РіРµРЅС‚Р° Р±РµР· РїСЂР°РІ,
> РѕРЅ СЂР°Р±РѕС‚Р°РµС‚ С€С‚Р°С‚РЅРѕ, РЅРѕ СЃРѕР±РёСЂР°РµС‚ 0 СЃРѕР±С‹С‚РёР№.

## Р—Р°РїСѓСЃРє

```powershell
# 1. Р—Р°РїСѓСЃС‚РёС‚СЊ Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Р—Р°РїСѓСЃС‚РёС‚СЊ Р°РіРµРЅС‚ (РёР· РїР°РїРєРё audit-agent)
cd audit-agent-windows
python main.py

# 3. Р›РёР±Рѕ РєР°Рє Windows-СЃР»СѓР¶Р±Сѓ (РѕС‚ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°)
cd audit-agent-windows
python service.py install
python service.py start
```

## РџСЂРѕРІРµСЂРєР°

```powershell
# РЎРѕР±С‹С‚РёСЏ РїРѕСЏРІРёР»РёСЃСЊ РІ Manager
curl "http://localhost:8000/api/audit?limit=10"

# РЎС‚Р°С‚СѓСЃ Р°РіРµРЅС‚Р° РІ Р‘Р”
curl "http://localhost:8000/api/audit/stats"
```

## РџРѕРІРµРґРµРЅРёРµ РїСЂРё РїРѕС‚РµСЂРµ СЃРІСЏР·Рё

Р•СЃР»Рё Manager РЅРµРґРѕСЃС‚СѓРїРµРЅ, СЃРѕР±С‹С‚РёСЏ РЅРµ СѓРґР°Р»СЏСЋС‚СЃСЏ: РѕРЅРё РєРѕРїСЏС‚СЃСЏ РІ SQLite-Р±СѓС„РµСЂРµ
(`buffer/buffer.db`, РјР°РєСЃРёРјСѓРј `buffer_size`) Рё РѕС‚РїСЂР°РІР»СЏСЋС‚СЃСЏ РїСЂРё РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРё СЃРІСЏР·Рё.
