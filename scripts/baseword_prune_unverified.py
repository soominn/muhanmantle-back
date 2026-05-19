"""
Preview/prune unverified BaseWord rows.

Usage:
  python -m scripts.baseword_prune_unverified --preview-limit 100
  python -m scripts.baseword_prune_unverified --delete --min-id 1
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.base_word import BaseWord


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Actually delete rows")
    parser.add_argument("--preview-limit", type=int, default=50)
    parser.add_argument("--min-id", type=int, default=1)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stmt = (
            select(BaseWord)
            .where(BaseWord.is_verified.is_(False))
            .where(BaseWord.id >= args.min_id)
            .order_by(BaseWord.id.asc())
        )
        preview = list(db.scalars(stmt.limit(args.preview_limit)))
        print(f"preview_count={len(preview)}")
        for row in preview:
            print(f"{row.id}\t{row.base_word}\t{row.verification_note}")

        if not args.delete:
            print("preview only (use --delete to apply)")
            return

        del_stmt = (
            delete(BaseWord)
            .where(BaseWord.is_verified.is_(False))
            .where(BaseWord.id >= args.min_id)
        )
        result = db.execute(del_stmt)
        db.commit()
        print(f"deleted={result.rowcount}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
