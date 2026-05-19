"""
Seed AnswerWord / BaseWord from muhanmantle-etc/wordlists.

  AnswerWord: 국어 기초 어휘 1~3등급 + Wiktionary 5800 (보조) → FastText vocab
  BaseWord:   국어원 단어 빈도순 상위 1만 (+ KoFREN, ko_50k 보조) → FastText vocab

Prerequisites:
  python scripts/download_wordlists.py
  pip install openpyxl beautifulsoup4 requests

Usage (from muhanmantle-back/):
  python scripts/seed_words.py
  python scripts/seed_words.py --skip-wiktionary
  python scripts/seed_words.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gensim.models import KeyedVectors
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS.parent))
sys.path.insert(0, str(_SCRIPTS))

from app.core.config import settings
from app.models.answer_word import AnswerWord
from app.models.base_word import BaseWord
from app.utils.word_input import is_valid_korean_word
from word_scraper import _load_kv_model, _upsert_words, fetch_words
import wordlist_loaders

DEFAULT_BASE_TARGET = 10_000


def _filter_vocab(words: list[str], kv: KeyedVectors) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        if not is_valid_korean_word(w):
            continue
        if w not in kv.key_to_index:
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AnswerWord and BaseWord tables")
    parser.add_argument(
        "--skip-wiktionary",
        action="store_true",
        help="Do not fetch Wiktionary 5800 for AnswerWord supplement",
    )
    parser.add_argument(
        "--base-target",
        type=int,
        default=DEFAULT_BASE_TARGET,
        help=f"Max BaseWord candidates before vocab filter (default {DEFAULT_BASE_TARGET})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not write to DB",
    )
    args = parser.parse_args()

    print("Loading FastText model …")
    kv = _load_kv_model()

    print("Loading AnswerWord candidates (NIKL grades 1–3) …")
    wiki: list[str] = []
    if not args.skip_wiktionary:
        print("Fetching Wiktionary 5800 (supplement) …")
        wiki = fetch_words()
        print(f"  Wiktionary: {len(wiki)} words")
    answer_raw = wordlist_loaders.build_answer_word_candidates(wiki or None)
    answer_words = _filter_vocab(answer_raw, kv)
    print(f"  AnswerWord: {len(answer_raw)} raw → {len(answer_words)} in FastText vocab")

    print("Loading BaseWord candidates (NIKL freq + KoFREN + ko_50k) …")
    base_raw = wordlist_loaders.build_base_word_candidates()
    base_words = _filter_vocab(base_raw, kv)[: args.base_target]
    print(
        f"  BaseWord: {len(base_raw)} raw → {len(base_words)} in FastText vocab "
        f"(cap {args.base_target})"
    )

    if args.dry_run:
        print("Dry run — no DB writes.")
        return

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        n_answer = _upsert_words(session, AnswerWord, "answer_word", answer_words)
        n_base = _upsert_words(session, BaseWord, "base_word", base_words)
    print(f"Inserted {n_answer} new AnswerWord(s), {n_base} new BaseWord(s).")
    print("Done. Optional: python -m scripts.baseword_dictionary_audit …")


if __name__ == "__main__":
    main()
