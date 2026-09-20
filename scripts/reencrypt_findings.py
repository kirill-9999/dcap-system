"""Перешифровка находок старым ключом на новый (ротация ключей Findings).

Использование:
    python scripts/reencrypt_findings.py \
        --old-key-file secrets/findings_encryption_key \
        --old-hmac-file secrets/findings_hmac_key \
        --new-key-file secrets/new/findings_encryption_key \
        --new-hmac-file secrets/new/findings_hmac_key \
        --new-key-id key-2026-12 \
        [--dry-run] [--batch-size 500] [--filter-key-id key-2026-09]

Логика:
- Подключение к БД через manager.src.config.get_config() (database.url).
- Выбирает findings WHERE encryption_key_id != :new_key_id
  [AND encryption_key_id = :filter_key_id].
- Расшифровывает match_text_encrypted / line_text_encrypted старым ключом
  и шифрует новым. Fingerprint НЕ пересчитывается (смена ключа сломает FP).
- Commit per batch. Идемпотентно: повторный запуск обрабатывает остаток.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manager.src.auth import models as auth_models  # noqa: E402  (mapper User)
from manager.src.config import get_config  # noqa: E402
from manager.src.core.encryption import FindingEncryption, _maybe_b64decode  # noqa: E402
from manager.src.db.models import Finding  # noqa: E402

logger = logging.getLogger("reencrypt_findings")


class _DecryptError(Exception):
    pass


class _EncryptError(Exception):
    pass


def load_key_file(path: str) -> bytes:
    """Читает ключ из файла: base64 (generate_findings_keys.py) или raw 32 байта."""
    data = Path(path).read_bytes().strip()
    return _maybe_b64decode(data)


def build_engine():
    cfg = get_config()
    url = cfg.get("database", {}).get("url")
    if not url:
        raise SystemExit("database.url не найден в конфиге (manager/config/config.json)")
    engine = create_engine(url)
    return engine


def reencrypt_value(old_enc, new_enc, value: Optional[str]) -> Optional[str]:
    """Расшифровывает старым и шифрует новым. ValueError при decrypt — skip row."""
    if not value:
        return value
    try:
        plain = old_enc.decrypt(value)
    except Exception as e:
        raise _DecryptError(f"decrypt: {e}") from e
    try:
        return new_enc.encrypt(plain)
    except Exception as e:
        raise _EncryptError(f"encrypt: {e}") from e


def run_reencrypt(
    engine,
    old_enc,
    new_enc,
    batch_size: int = 500,
    filter_key_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Перешифровывает findings. Возвращает итоговый отчёт.
    При ошибке decrypt — пропускает строку; при ошибке encrypt — rollback батча и abort.
    """
    total = 0
    already_new = 0
    processed = 0
    skipped = 0
    skipped_ids = []

    with Session(engine) as db:
        total = db.query(Finding).count()
        already_new = db.query(Finding).filter(
            Finding.encryption_key_id == new_enc.key_id
        ).count()

        base_q = db.query(Finding).filter(
            Finding.encryption_key_id != new_enc.key_id
        )
        if filter_key_id:
            base_q = base_q.filter(Finding.encryption_key_id == filter_key_id)

        last_id = 0
        while True:
            rows = (
                base_q.filter(Finding.id > last_id)
                .order_by(Finding.id)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break

            to_commit = True
            for f in rows:
                try:
                    new_match = reencrypt_value(old_enc, new_enc, f.match_text_encrypted)
                    new_line = reencrypt_value(old_enc, new_enc, f.line_text_encrypted)
                except _DecryptError as e:
                    logger.error("skip finding %s: %s", f.id, e)
                    skipped += 1
                    skipped_ids.append(f.id)
                    continue
                except _EncryptError as e:
                    logger.error("batch aborted at finding %s: %s", f.id, e)
                    db.rollback()
                    to_commit = False
                    break

                f.match_text_encrypted = new_match
                f.line_text_encrypted = new_line
                f.encryption_key_id = new_enc.key_id
                processed += 1
                last_id = f.id

            if not to_commit:
                break

            if rows:
                last_id = max(last_id, rows[-1].id)

            if not dry_run and to_commit:
                db.commit()
            if dry_run:
                db.rollback()

            print(f"Processed: {processed} / {total}")

    return {
        "total": total,
        "already_new": already_new,
        "reencrypted": processed,
        "skipped": skipped,
        "batch_size": batch_size,
        "dry_run": dry_run,
        "skipped_ids": skipped_ids,
    }


def print_report(stats: dict):
    verb = "complete (dry-run, no writes)" if stats["dry_run"] else "complete"
    print("\nReencryption " + verb + ".")
    print(f"  Total findings:     {stats['total']}")
    print(f"  Already new key:    {stats['already_new']}")
    print(f"  Reencrypted:        {stats['reencrypted']}")
    print(f"  Skipped (error):    {stats['skipped']}")
    print(f"  Batch size:         {stats['batch_size']}")
    if stats["skipped_ids"]:
        print(f"  Skipped ids:        {stats['skipped_ids']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Перешифровка находок старым ключом на новый"
    )
    parser.add_argument("--old-key-file", required=True)
    parser.add_argument("--old-hmac-file", required=True)
    parser.add_argument("--new-key-file", required=True)
    parser.add_argument("--new-hmac-file", required=True)
    parser.add_argument("--new-key-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--filter-key-id", default=None)
    args = parser.parse_args(argv)

    old_enc = FindingEncryption(
        key=load_key_file(args.old_key_file),
        hmac_key=load_key_file(args.old_hmac_file),
        key_id="key-old",
    )
    new_enc = FindingEncryption(
        key=load_key_file(args.new_key_file),
        hmac_key=load_key_file(args.new_hmac_file),
        key_id=args.new_key_id,
    )

    engine = build_engine()
    stats = run_reencrypt(
        engine=engine,
        old_enc=old_enc,
        new_enc=new_enc,
        batch_size=args.batch_size,
        filter_key_id=args.filter_key_id,
        dry_run=args.dry_run,
    )
    print_report(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())