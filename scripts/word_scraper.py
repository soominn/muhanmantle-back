"""
Wiktionary word scraper — seeds AnswerWord and BaseWord tables from
the Korean top-5800 frequency word list.

Usage (from muhanmantle-back/):
    python scripts/word_scraper.py
"""

import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from gensim.models import KeyedVectors
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Allow `from app.*` imports when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models.answer_word import AnswerWord
from app.models.base_word import BaseWord

WIKTIONARY_URL = (
    "https://ko.wiktionary.org/wiki/"
    "%EB%B6%80%EB%A1%9D:%EC%9E%90%EC%A3%BC_%EC%93%B0%EC%9D%B4%EB%8A%94_"
    "%ED%95%9C%EA%B5%AD%EC%96%B4_%EB%82%B1%EB%A7%90_5800"
)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _load_kv_model() -> KeyedVectors:
    kv = settings.kv_file
    vec = settings.vec_file
    if Path(kv).exists():
        return KeyedVectors.load(kv)
    model = KeyedVectors.load_word2vec_format(vec, binary=False, unicode_errors="ignore")
    model.save(kv)
    return model


def fetch_words() -> list[str]:
    try:
        resp = requests.get(WIKTIONARY_URL, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    elements = soup.select("table.prettytable tbody tr td dl dd a")
    return list({el.get_text().strip() for el in elements if len(el.get_text().strip()) > 1})


def _upsert_words(session, model_cls, field: str, words: list[str]) -> int:
    existing = set(
        session.scalars(
            select(getattr(model_cls, field)).where(
                getattr(model_cls, field).in_(words)
            )
        )
    )
    new_words = [w for w in words if w not in existing]
    if new_words:
        session.bulk_save_objects([model_cls(**{field: w}) for w in new_words])
        session.commit()
    return len(new_words)


def main() -> None:
    print("Loading FastText model …")
    kv_model = _load_kv_model()

    print("Fetching words from Wiktionary …")
    words = fetch_words()
    if not words:
        print("No words fetched. Exiting.")
        return
    print(f"Fetched {len(words)} unique words.")

    # Only keep words that exist in the FastText vocab
    in_vocab = [w for w in words if w in kv_model.key_to_index]
    print(f"{len(in_vocab)} words found in FastText vocab.")

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        n_answer = _upsert_words(session, AnswerWord, "answer_word", in_vocab)
        n_base = _upsert_words(session, BaseWord, "base_word", in_vocab)
    print(f"Inserted {n_answer} new AnswerWord(s), {n_base} new BaseWord(s).")
    print("Done.")


if __name__ == "__main__":
    main()
