# tests/e2e/test_key_rotation.py — E2E-тест ротации ключей Findings (TASK-020).
#
# Сценарий по ТЗ (изолированный тестовый стек, offline — Manager не требуется):
#   1. Setup    — генерируем key-test-01 (generate_findings_keys.py),
#                 создаём 100 findings в temp-БД с этим ключом.
#   2. Ротация  — генерируем key-test-02, запускаем reencrypt_findings.py
#                 (старый ключ -> новый), обновляем "ENV".
#   3. Verify   — все findings на key-test-02, данные расшифровываются новым ключом,
#                 старый ключ больше не нужен.
#
# Live-прогон через API (POST /api/findings/{id}/reveal + GET /api/findings/{id})
# выполняется вручную по docs/admin-guide/05-security.md §3 — здесь тестируется
# контракт шифрования + конвейер перешифровки.
import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e_offline]

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.core.encryption import FindingEncryption  # noqa: E402
from manager.src.db import models  # noqa: E402
from manager.src.auth import models as auth_models  # noqa: E402  (таблица users)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

PY = sys.executable


def _run_cli(args, env=None, expected=(0,)):
    """Запуск скрипта из scripts/ как subprocess."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    p = subprocess.run(
        [PY, str(ROOT / args[0]), *args[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=120,
        cwd=str(ROOT),
    )
    if p.returncode not in expected:
        raise AssertionError(
            f"{args} exited {p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p


def _env_for(secrets_dir: Path) -> dict:
    """base64 содержимое файлов ключей -> dict плейсхолдеров MANAGER_CONFIG."""
    env = dict(os.environ)
    env["FINDINGS_ENCRYPTION_KEY"] = (secrets_dir / "findings_encryption_key").read_text().strip()
    env["FINDINGS_HMAC_KEY"] = (secrets_dir / "findings_hmac_key").read_text().strip()
    env["FINDINGS_KEY_ID"] = (secrets_dir / "findings_key_id").read_text().strip()
    return env


@pytest.fixture(scope="module")
def rotation_stack(tmp_path_factory):
    """temp-стек: БД + старые/новые ключи + MANAGER_CONFIG."""
    tmp = tmp_path_factory.mktemp("key_rotation")

    secrets_old = tmp / "secrets"
    secrets_new = tmp / "secrets" / "new"

    _run_cli(["scripts/generate_findings_keys.py", "--key-id", "key-test-01", "--output", str(secrets_old)])
    _run_cli(["scripts/generate_findings_keys.py", "--key-id", "key-test-02", "--output", str(secrets_new)])

    db_file = tmp / "e2e_rotation.db"
    cfg = tmp / "manager_config.json"
    cfg.write_text(
        '{"database": {"url": "sqlite:///%s"}}\n' % db_file.as_posix(),
        encoding="utf-8",
    )

    env_old = _env_for(secrets_old)
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    enc = FindingEncryption(
        key=base64.b64decode(env_old["FINDINGS_ENCRYPTION_KEY"]),
        hmac_key=base64.b64decode(env_old["FINDINGS_HMAC_KEY"]),
        key_id="key-test-01",
    )
    with Session() as db:
        for i in range(100):
            plain = f"secret-rot-{i}"
            db.add(
                models.Finding(
                    resource_id=1,
                    finding_type="credentials",
                    category="password",
                    fragment_type="text_line",
                    line_number=i,
                    match_text_masked=plain.replace("secret", "***"),
                    match_text_encrypted=enc.encrypt(plain),
                    fingerprint=enc.fingerprint(f"/f{i}.env", i, plain, "credentials"),
                    encryption_key_id="key-test-01",
                )
            )
        db.commit()

    return {
        "tmp": tmp,
        "db_file": db_file,
        "cfg": cfg,
        "secrets_old": secrets_old,
        "secrets_new": secrets_new,
        "engine": engine,
        "env_old": env_old,
    }


def _rows(stack) -> list:
    with stack["engine"].connect() as conn:
        rows = conn.execute(
            text("SELECT id, match_text_encrypted, encryption_key_id FROM findings ORDER BY id")
        ).all()
    return rows


def test_rotation_preserves_data(rotation_stack):
    """100 findings на key-test-01 -> после ротации все на key-test-02, данные целы."""
    stack = rotation_stack
    with stack["engine"].connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM findings")).scalar()
    assert total == 100
    with stack["engine"].connect() as conn:
        old_cnt = conn.execute(
            text("SELECT COUNT(*) FROM findings WHERE encryption_key_id='key-test-01'")
        ).scalar()
    assert old_cnt == 100, "Setup: все findings должны быть на key-test-01"

    # Ротация: старый -> новый
    p = _run_cli(
        ["scripts/reencrypt_findings.py",
         "--old-key-file", str(stack["secrets_old"] / "findings_encryption_key"),
         "--old-hmac-file", str(stack["secrets_old"] / "findings_hmac_key"),
         "--new-key-file", str(stack["secrets_new"] / "findings_encryption_key"),
         "--new-hmac-file", str(stack["secrets_new"] / "findings_hmac_key"),
         "--new-key-id", "key-test-02",
         "--batch-size", "25"],
        env={"MANAGER_CONFIG": str(stack["cfg"])},
    )
    assert "Reencryption complete" in p.stdout

    with stack["engine"].connect() as conn:
        new_cnt = conn.execute(
            text("SELECT COUNT(*) FROM findings WHERE encryption_key_id='key-test-02'")
        ).scalar()
    assert new_cnt == 100, f"После ротации все на key-test-02: {new_cnt}"

    # Данные не потеряны: расшифровка новым ключом даёт исходный plaintext
    new_env = _env_for(stack["secrets_new"])
    new_enc = FindingEncryption(
        key=base64.b64decode(new_env["FINDINGS_ENCRYPTION_KEY"]),
        hmac_key=base64.b64decode(new_env["FINDINGS_HMAC_KEY"]),
        key_id="key-test-02",
    )
    rows = _rows(stack)
    assert len(rows) == 100
    for rid, ct, kid in rows:
        assert kid == "key-test-02", rid
        assert new_enc.decrypt(ct) == f"secret-rot-{rid - 1}", rid


def test_reveal_after_rotation(rotation_stack):
    """Reveal-путь после ротации: decrypt по новому ключу из 'ENV' работает."""
    stack = rotation_stack
    new_env = _env_for(stack["secrets_new"])

    # Эмуляция обновлённого ENV Manager'а (п. «Обновить ENV -> перезапустить»)
    os_env_backup = {k: os.environ.get(k) for k in ("FINDINGS_ENCRYPTION_KEY",
                                                     "FINDINGS_HMAC_KEY",
                                                     "FINDINGS_KEY_ID")}
    os.environ["FINDINGS_ENCRYPTION_KEY"] = new_env["FINDINGS_ENCRYPTION_KEY"]
    os.environ["FINDINGS_HMAC_KEY"] = new_env["FINDINGS_HMAC_KEY"]
    os.environ["FINDINGS_KEY_ID"] = "key-test-02"

    from manager.src.core.encryption import reset_encryption, get_encryption

    try:
        reset_encryption()
        enc = get_encryption()
        assert enc.key_id == "key-test-02", enc.key_id
        rows = _rows(stack)
        for rid, ct, kid in rows:
            plain = enc.decrypt(ct)  # путь reveal: расшифровка рабочим ключом
            assert plain.startswith("secret-rot-")
        reset_encryption()
    finally:
        for k, v in os_env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_old_key_not_required_after_rotation(rotation_stack):
    """После ротации старый ключ больше не нужен: decrypt работает без old-файлов."""
    stack = rotation_stack
    new_env = _env_for(stack["secrets_new"])

    # Удаляем старые ключи — как в реальной ротации
    for f in ("findings_encryption_key", "findings_hmac_key", "findings_key_id"):
        (stack["secrets_old"] / f).unlink()

    os_env_backup = {}
    for k in ("FINDINGS_ENCRYPTION_KEY", "FINDINGS_HMAC_KEY", "FINDINGS_KEY_ID"):
        os_env_backup[k] = os.environ.get(k)
    os.environ["FINDINGS_ENCRYPTION_KEY"] = new_env["FINDINGS_ENCRYPTION_KEY"]
    os.environ["FINDINGS_HMAC_KEY"] = new_env["FINDINGS_HMAC_KEY"]
    os.environ["FINDINGS_KEY_ID"] = "key-test-02"

    from manager.src.core.encryption import reset_encryption, get_encryption

    plaintexts = []
    try:
        reset_encryption()
        enc = get_encryption()
        for _rid, ct, _kid in _rows(stack):
            plaintexts.append(enc.decrypt(ct))
        reset_encryption()
    finally:
        for k, v in os_env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    assert len(plaintexts) == 100
    assert all(p.startswith("secret-rot-") for p in plaintexts)