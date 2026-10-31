# DCAP ‚Äî Data Classification & Audit Platform

[![Version](https://img.shields.io/badge/version-3.0.0-blue)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Docker](https://img.shields.io/badge/docker-compose-blue)](docker-compose.yml)
[![Tests](https://img.shields.io/badge/tests-544%20passed-brightgreen)](tests/)

> **DCAP** ‚Äî ü–ª–∞—Ç—Ñ–æ—Ä–º–∞ –∞—É–¥–∏—Ç–∞ –¥–∞–Ω–Ω—ã—Ö –Ω–∞ –ø—Ä–µ–¥–º–µ—Ç –∫–æ–Ω—Ñ–∏–¥–µ–Ω—Ü–∏–∞–ª—å–Ω–æ–π –∏–Ω—Ñ–æ—Ä–º–∞—Ü–∏–∏ (PII, credentials,
> code secrets) –∏ —Ä–∞–∑—Ä–µ—à–µ–Ω–∏–π –Ω–∞ —Ñ–∞–π–ª–æ–≤—ã—Ö —Ö—Ä–∞–Ω–∏–ª–∏—â–∞—Ö –∏ S3/MinIO. Enterprise-ready: RBAC, mTLS,
> —Å–æ–æ—Ç–≤–µ—Ç—Å—Ç–≤–∏–µ —Ä–µ–≥—É–ª—è—Ç–æ—Ä–∞–º (152-–§–ó / GDPR / PCI DSS), retention, Prometheus/Grafana.

## ‚ú® –í–æ–∑–º–æ–∂–Ω–æ—Å—Ç–∏

- **–°–∫–∞–Ω–µ—Ä** ‚Äî PII (F–ò–û, email, —Ç–µ–ª–µ—Ñ–æ–Ω—ã, –ø–∞—Å–ø–æ—Ä—Ç–∞, –°–ù–ò–õ–°, –ò–ù–ù, –±–∞–Ω–∫–æ–≤—Å–∫–∏–µ –∫–∞—Ä—Ç—ã), credentials
  (API-–∫–ª—é—á–∏, –ø–∞—Ä–æ–ª–∏, SSH, —Ç–æ–∫–µ–Ω—ã), code secrets. OCR –¥–ª—è –∏–∑–æ–±—Ä–∞–∂–µ–Ω–∏–π/PDF.
- **–ê—É–¥–∏—Ç —Ä–∞–∑—Ä–µ—à–µ–Ω–∏–π** ‚Äî —Ñ–∞–π–ª–æ–≤—ã–µ —Ö—Ä–∞–Ω–∏–ª–∏—â–∞ (Windows/Linux), S3/MinIO (streaming, multipart).
- **–®–∏—Ñ—Ä–æ–≤–∞–Ω–∏–µ** ‚Äî AES-256-GCM; —Ä–∞—Å—à–∏—Ñ—Ä–æ–≤–∫–∞ —Ç–æ–ª—å–∫–æ Auditor, —Å –∞—É–¥–∏—Ç–æ–º.
  HMAC-SHA256 fingerprint (–∑–∞—â–∏—Ç–∞ –æ—Ç brute-force). –ú–∞—Å–∫–∏—Ä–æ–≤–∞–Ω–∏–µ –∫–æ–Ω—Ç–µ–∫—Å—Ç–æ–≤
  –Ω–∞ —Å—Ç–æ—Ä–æ–Ω–µ Manager (BUG-117).
- **–î–∞—à–±–æ—Ä–¥** ‚Äî —Ñ–∏–ª—å—Ç—Ä—ã –ø–æ findings, —Å—Ç–∞—Ç–∏—Å—Ç–∏–∫–∞, —ç–∫—Å–ø–æ—Ä—Ç; –∞—É–¥–∏—Ç Windows/Linux/S3.
- **RBAC** ‚Äî admin / auditor / scanner / viewer; AD-–∏–Ω—Ç–µ–≥—Ä–∞—Ü–∏—è; mTLS relaxed/strict.
- **Retention** ‚Äî –ø–æ–ª–∏—Ç–∏–∫–∏ TTL, –æ—á–∏—Å—Ç–∫–∞, –∞—Ä—Ö–∏–≤–∏—Ä–æ–≤–∞–Ω–∏–µ, Celery Beat.
- **–ú–æ–Ω–∏—Ç–æ—Ä–∏–Ω–≥** ‚Äî Prometheus /metrics, Grafana (2 –¥–∞—à–±–æ—Ä–¥–∞, 4 –∞–ª–µ—Ä—Ç–∞).
- **WebUI** ‚Äî Dovetail dark, RBAC-–≥–µ–π—Ç—ã, responsive.

## ‚öôÔ∏è –†–µ–∫–≤–∏–∑–∏—Ç—ã<c/br>

- Docker + Docker Compose v2 (`--wait`)
- Python 3.10+ (–¥–ª—è —Å–∫–∞–Ω–µ—Ä–∞ –Ω–∞ —Ö–æ—Å—Ç–µ)
- 16 –ì–ë RAM (—Å–∫–∞–Ω–µ—Ä: `max_workers=2`; 32 –ì–ë ‚Üí 4; 128 –ì–ë ‚Üí 8)

<h3>1. –ö–ª–æ–Ω–∏—Ä–æ–≤–∞—Ç—å –∏ –Ω–∞—Å—Ç—Ä–æ–∏—Ç—å</h3>

```bash
git clone https://github.com/kirill-9999/dcap-system.git
cd dcap-system
cp .env.example .env
# –ó–∞–ø–æ–ª–Ω–∏—Ç—å: FINDINGS_ENCRYPTION_KEY, FINDINGS_HMAC_KEY (base64, 32 bytes),
#           S3_ACCESS_KEY, S3_SECRET_KEY (–µ—Å–ª–∏ S3), POSTGRES_PASSWORD
```

–ì–µ–Ω–µ—Ä–∞—Ü–∏—è –∫–ª—é—á–µ–π findings:

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
# –ø–æ–≤—Ç–æ—Ä–∏—Ç—å –¥–≤–∞–∂–¥—ã ‚Äî –¥–ª—è FINDINGS_ENCRYPTION_KEY –∏ FINDINGS_HMAC_KEY
```

<h3>2. –ü–æ–¥–Ω—è—Ç—å —Å—Ç–µ–∫</h3>

```bash
docker compose up -d --build --wait
# Manager :8000, WebUI :8001, Grafana :3000, Prometheus :9090
```

<h3>3. –ü–µ—Ä–≤—ã–π –≤—Ö–æ–¥</h3>

WebUI: http://localhost:8001

–õ–æ–≥–∏–Ω: admin / admin123 ‚Äî —Å–º–µ–Ω–∏—Ç—å –ø—Ä–∏ –ø–µ—Ä–≤–æ–º –∑–∞–ø—É—Å–∫–µ (Settings ‚Üí Password).

<h3>4. –ó–∞–ø—É—Å—Ç–∏—Ç—å —Å–∫–∞–Ω–µ—Ä (–Ω–∞ —Ö–æ—Å—Ç–µ)</h3>

```bash
export FINDINGS_ENCRYPTION_KEY="<base64>"
export FINDINGS_HMAC_KEY="<base64>"
export MANAGER_URL="http://127.0.0.1:8000"
python run_scanner.py scanner/config/scanner_config.json
```

‚ùóÔ∏è –í production —Å–∫–∞–Ω–µ—Ä –±–µ–∑ –∫–ª—é—á–µ–π –Ω–µ —Å—Ç–∞—Ä—Ç—É–µ—Ç (fail-fast).
DCAP_ALLOW_LEGACY_SCANNER=true ‚Äî —Ç–æ–ª—å–∫–æ dev.

<h3>5. –°–æ–∑–¥–∞—Ç—å —Ä–µ—Å—É—Ä—Å –∏ –∑–∞–ø—É—Å—Ç–∏—Ç—å —Å–∫–∞–Ω</h3>

WebUI ‚Üí Resources ‚Üí New (filesystem path –∏–ª–∏ s3://bucket/prefix).

–ò–ª–∏ API: `POST /api/resources?path=...&type=filesystem` ‚Üí `POST /api/resources/{id}/scan`.

## üèóÔ∏è –ê—Ä—Ö–∏—Ç–µ–∫—Ç—É—Ä–∞

![–ê—Ä—Ö–∏–µ–∫—Ç—É—Ä–∞ DCAP](docs/architecture-overview.png)

–û–±—â–∞—è —Å—Ö–µ–º–∞ –≤–∑–∞–∏–º–æ–¥–µ–π—Å—Ç–≤–∏—è –∫–æ–º–ø–æ–Ω–µ–Ω—Ç–æ–≤ DCAP (Manager, Scanner, –∞–≥–µ–Ω—Ç—ã, —Ö—Ä–∞–Ω–∏–ª–∏—â–∞).

Pæ–¥—Ä–æ–±–Ω–æ–µ –æ–ø–∏—Å–∞–Ω–∏–µ (–º–æ–¥–µ–ª–∏ –¥–∞–Ω–Ω—ã—Ö, API, SIEM)‚Äî –≤ ARCHITECTURE.md –∏ docs/architecture.mermaid.

## üß§ –¢–µ—Å—Ç–∏—Ä–æ–≤–∞–Ω–∏–µ

```bash
# Unit (544 passed)
pytest tests/unit -q

# E2E (—Ç–µ—Å—Ç–æ–≤—ã–π —Å—Ç–µ–Ω–¥ :18000/:18001)
scripts/test-up.sh
scripts/run-tests.sh e2e

# Security (53.5)
scripts/security_scan.ps1   # Bandit, Semgrep, Gitleaks, pip-audit, Trivy, ZAP
```

–ü–æ–¥—Ä–æ–±–Ω–µ–µ ‚Äî docs/testing.md.

## üìö –î–æ–∫—É–º–µ–Ω—Ç–∞—Ü–∏—è

-ARCHITECTUDE.md ‚Äî –∞—Ä—Ö–∏—Ç–µ–∫—Ç—É—Ä–∞, –º–æ–¥–µ–ª–∏, API, SIEM.
-ROADMAP.md ‚Äî –ø–ª–∞–Ω –∏ –±—ç–∫–ª–æ–≥.
-CHANGELOG.md ‚Äî –∏—Å—Ç–æ—Ä–∏—è –∏–∑–º–µ–Ω–µ–Ω–∏–π.
-docs/admin-guide/ ‚Äî 04-authentication, 05-security, 06-scanner, 10-troubleshooting.
-docs/DESIGN.md ‚Äî WebUI style reference (Dovetail).
-QMUI%QdπµêÉäPÉBˇB˚BÔB„FB„BÎB¿ÉB«B◊BﬂB˚BˇB√FB˜B˚FFB‡∏(µëΩçÃΩÕïç’…•—Â}ç°ïç≠±•Õ–πµê∏((ååÉ¬~RPÉBGB◊BﬂB˚BˇB√FB˜B˚FFF0((µ•πë•πùÃËÅL¥»‘ÿµ4Ä¨Å!5µM!»‘ÿÅô•πùï…¡…•π–ÏÉBÛB√FBÎB„FB˚BÀB√B˜B„B‘ÉBˇB¯ÉFBÛB˚BÔFB√B˜B„F8∏(∑BÉB√FF#B„FFB˚BÀBÎB¿ÉäPÉFB˚BÔF3BÎB¯Å’ë•—Ω»∞ÉFÉB√FB”B„FB˚BÄ°ô•πë•πù}…ïŸïÖ∞§∏(µµQ1LÅ…ï±Ö·ïêΩÕ—…•ç–Ä¨ÅI0ÏÅµÖç°•πî∑F7B˜B”BˇB˚B„B˜FF,ÉBˇFB˚BÀB◊FF?F;FÉFB◊FFB„FB„BÎB√FÉB»ÅÕ—…•ç–∏(∑BCFB”B„FËÅô•πë•πùÃ∞ÅÖ’—†∞ÉFB˚BÔB‡∞Å…ï—ïπ—•Ω∏ÉäPÉÇ»ÅÖ’ë•—}±ΩùÃÄ£BˇB√FFB„FB„B˚B˜B„FB˚BÀB√B˜B„B‘§∏(¥‘Ã∏‘ËÅ	Öπë•–Ä¿Å!% ∞ÅMïµù…ï¿Ä¿∞Å•—±ïÖ≠ÃÄ¿∞Å¡•¿µÖ’ë•–Ä¿∞ÅQ…•Ÿ‰Ä¿ÅI%Q%0∞(ÄÅi@Ä¿Å!% ∞ÅÖ¡…Ω¿ım11t∞ÅπΩ∏µ…ΩΩ–∏(∑äjÉæ‚<ÄΩµï—…•çÃÉBˇFB«BÔB„FB˜F/B‰Ä°	-1=¥¿––§ÉäPÉBﬂB√BÎFF/FF0ÉB»Å¡…Ωë’ç—•Ω∏∏(∑äjÉæ‚<ÅÖëµ•∏ΩÖëµ•∏ƒ»ÃÉäPÉFBÛB◊B˜B„FF0ÉBˇFB‡ÉBˇB◊FBÀB˚BÉBﬂB√BˇFFBÎB‘∏(µroBÁB”B◊B˜B˜F/B‘ÉFF?BﬂBÀB„BÛB˚FFB‡ÉäPÉFB∏ÅMUI%Qdπµê∏((ååÉ¬~íTÅΩπ—…•â’—•πú()Ω…¨ÉäHÅâ…Öπç†ÉäHÅAH∏(+BãB◊FFF,ËÅÅ¡Â—ïÕ–Å—ïÕ—ÃΩ’π•–Äµ≈ÄÄ¨ÅÅÕç…•¡—ÃΩ…’∏µ—ïÕ—ÃπÕ†Åî…ïÄÄ£BˇFB‡ÉBˇFB◊B”FFBÔB˚BÀB„F?F§∏(+BáFB„BÔF0ËÅA@Ä‡∞Å—Â¡îÅ°•π—Ã∞Å±Ωùùï»ÉBÀBÛB◊FFB¯Å¡…•π–∏()Mïç’…•—‰∑BˇFB√BÀBÎB‡ÉäPÅÃÄåÅπΩÕïµù…ï¿Ä¨ÉBÎB˚BÛBÛB◊B˜FB√FB„B◊BÄ£B◊FBÔB‡ÉB˚FB˚BﬂB˜B√B˜B˜B¯§Ä∏()$ÉäPÅ•—!’àÅç—•ΩπÃÄ°	-1=¥¿–ÿ∞ÉB”B◊B˜F0Ä‘‘§∏((ååÉ¬~NÉBoB„FB◊B˜BﬂB„F<()¡Öç°îÅ1•çïπÕîÄ»∏¿∏ÉBáFB˚FB˚B˜B˜B„B‘ÉBÎB˚BÛBˇB˚B˜B◊B˜FF,ÉäPÉFB∏Å9=Q%πµê∏((ååÉ¬~f<Åç≠πΩ›±ïëùïµïπ—Ã((¥Å%π—ï»Ä°…ÕµÃΩ•π—ï»§ÉäPÅM%0Å=0Äƒ∏ƒ(¥¶WFBGB◊FB„B˜FF,Å5ΩπºÉäPÅM%0Å=0Äƒ∏ƒ(¥Å	ΩΩ—Õ—…Ö¿∞Å°Ö…–π©Ã∞ÅΩπ–Å›ïÕΩµîÉäPÅ5%PÄºÅ	MÄ£FB∏Å9=Q%πµê§((ååÉ¬~N∞ÉBkB˚B˜FB√BÎFF,()%ÕÕ’ïÃËÅ°——¡ÃËºΩù•—°’àπçΩ¥Ω≠•…•±∞¥‰‰‰‰ΩëçÖ¿µÕÂÕ—ï¥Ω•ÕÕ’ïÃ()Mïç’…•—‰ËÉFB∏ÅMUI%Qdπµ
