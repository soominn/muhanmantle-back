"""
Audit simword_baseword entries with Stdict (표준국어대사전) search API.

Batch mode:
  python -m scripts.baseword_dictionary_audit --batch-size 25000
  (processes verification_source IS NULL rows only, ordered by id)

Single row by id:
  python -m scripts.baseword_dictionary_audit --id 12345
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from sqlalchemy import select
from tqdm import tqdm

from app.db.session import SessionLocal
from app.models.base_word import BaseWord
from app.services.stdict_openapi import fetch_search_json, word_found_in_search_response


def _load_dotenv_if_present() -> None:
    """Minimal .env loader for standalone script runs."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip("\"").strip("'")
        os.environ[key] = value


def _audit_stdict(
    db,
    *,
    api_key: str,
    dry_run: bool,
    sleep_sec: float,
    limit: int | None,
    commit_every: int,
) -> None:
    q = select(BaseWord).order_by(BaseWord.id)
    q = q.where(BaseWord.verification_source.is_(None))
    if limit is not None:
        q = q.limit(limit)
    rows = list(db.scalars(q))
    total = len(rows)
    matched = 0
    unmatched = 0
    errors = 0

    pbar = tqdm(rows, total=total, desc="audit stdict", unit="word")
    for i, row in enumerate(pbar, start=1):
        try:
            payload = fetch_search_json(
                row.base_word,
                key=api_key,
            )
            ok = word_found_in_search_response(row.base_word, payload)
        except Exception as e:
            errors += 1
            print(f"ERR id={row.id} word={row.base_word!r}: {e}")
            pbar.set_postfix(
                matched=matched,
                unmatched=unmatched,
                errors=errors,
                refresh=True,
            )
            continue

        if ok:
            row.is_verified = True
            row.verification_source = "stdict"
            row.verification_note = None
            matched += 1
        else:
            row.is_verified = False
            row.verification_source = "stdict"
            row.verification_note = "no_exact_word_match"
            unmatched += 1

        if commit_every > 0 and i % commit_every == 0 and not dry_run:
            db.commit()

        if sleep_sec > 0:
            time.sleep(sleep_sec)

        pbar.set_postfix(
            matched=matched,
            unmatched=unmatched,
            errors=errors,
            refresh=False,
        )
    pbar.close()

    print(
        f"processed={total} matched={matched} unmatched={unmatched} errors={errors} "
        f"(verification_source IS NULL, limit={limit})"
    )
    if dry_run:
        db.rollback()
        print("dry-run: rolled back")
    else:
        db.commit()
        print("committed")


def _audit_single_id(
    db,
    *,
    row_id: int,
    api_key: str,
    dry_run: bool,
) -> None:
    row = db.get(BaseWord, row_id)
    if row is None:
        raise SystemExit(f"BaseWord id={row_id} not found.")

    try:
        payload = fetch_search_json(row.base_word, key=api_key)
        ok = word_found_in_search_response(row.base_word, payload)
    except Exception as e:
        raise SystemExit(f"Lookup failed for id={row_id} word={row.base_word!r}: {e}") from e

    if ok:
        row.is_verified = True
        row.verification_source = "stdict"
        row.verification_note = None
    else:
        row.is_verified = False
        row.verification_source = "stdict"
        row.verification_note = "no_exact_word_match"

    print(
        f"id={row.id} word={row.base_word} verified={row.is_verified} "
        f"source={row.verification_source} note={row.verification_note}"
    )

    if dry_run:
        db.rollback()
        print("dry-run: rolled back")
    else:
        db.commit()
        print("committed")


def main() -> None:
    _load_dotenv_if_present()

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stdict-key", default=os.environ.get("STDICT_API_KEY", ""))
    parser.add_argument("--id", type=int, default=None, help="Audit only this BaseWord id")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds between requests",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25000,
        help="Rows per batch (default: 25000)",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=50,
        help="Commit every N rows during batch mode (0 = single commit at end)",
    )

    args = parser.parse_args()
    api_key = (args.stdict_key or "").strip()
    if not api_key:
        raise SystemExit("STDICT_API_KEY is required (or --stdict-key).")

    db = SessionLocal()
    try:
        if args.id is not None:
            _audit_single_id(
                db,
                row_id=int(args.id),
                api_key=api_key,
                dry_run=args.dry_run,
            )
        else:
            batch_size = max(1, int(args.batch_size))
            limit = batch_size
            print(
                "Running batch size="
                f"{batch_size} (verification_source IS NULL only, ordered by id)"
            )

            ce = max(0, int(args.commit_every))
            _audit_stdict(
                db,
                api_key=api_key,
                dry_run=args.dry_run,
                sleep_sec=max(0.0, float(args.sleep)),
                limit=limit,
                commit_every=ce,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
