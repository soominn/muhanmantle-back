"""
Naver news crawler — extracts frequent Korean nouns and populates BaseWord.

Usage (from muhanmantle-back/):
    python scripts/news_word_analysis.py          # run once immediately
    python scripts/news_word_analysis.py --loop   # run on schedule (daily 00:00)

Dependencies (not in main requirements.txt — install separately):
    pip install beautifulsoup4 requests konlpy schedule
"""

import sys
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models.base_word import BaseWord

NAVER_POPULAR_URL = "https://news.naver.com/main/ranking/popularDay.naver"
MAX_ARTICLES = 50
TOP_WORDS = 50
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def get_popular_articles() -> list[str]:
    try:
        resp = requests.get(NAVER_POPULAR_URL, headers=HEADERS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"Page load failed: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("div.rankingnews_box a.list_title[href]")

    articles: list[str] = []
    seen: set[str] = set()

    for link in links:
        url = link["href"]
        if not url.startswith("http"):
            url = "https://news.naver.com" + url
        if url in seen:
            continue
        seen.add(url)

        try:
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
        except requests.RequestException:
            continue

        content = BeautifulSoup(r.text, "html.parser").select_one("#dic_area")
        if content:
            text = content.get_text(strip=True)
            if text not in articles:
                articles.append(text)

        if len(articles) >= MAX_ARTICLES:
            break
        time.sleep(1)

    return articles


def extract_frequent_nouns(texts: list[str]) -> list[tuple[str, int]]:
    from konlpy.tag import Okt  # optional dep — imported lazily

    okt = Okt()
    all_nouns: list[str] = []
    for text in texts:
        all_nouns.extend(n for n in okt.nouns(text) if len(n) > 1)
    return Counter(all_nouns).most_common(TOP_WORDS)


def save_words(words: list[tuple[str, int]]) -> int:
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    word_strs = [w for w, _ in words]

    with Session() as session:
        existing = set(
            session.scalars(
                select(BaseWord.base_word).where(BaseWord.base_word.in_(word_strs))
            )
        )
        new = [BaseWord(base_word=w) for w in word_strs if w not in existing]
        if new:
            session.bulk_save_objects(new)
            session.commit()
    return len(new) if new else 0


def run_once() -> None:
    print("Collecting Naver popular articles …")
    articles = get_popular_articles()
    if not articles:
        print("No articles collected.")
        return
    print(f"Analysing {len(articles)} articles …")
    top_words = extract_frequent_nouns(articles)
    print("\nTop words:")
    for rank, (word, count) in enumerate(top_words, 1):
        print(f"  {rank:2d}. {word} ({count})")
    inserted = save_words(top_words)
    print(f"Inserted {inserted} new word(s) into BaseWord.")


def main() -> None:
    if "--loop" in sys.argv:
        import schedule

        schedule.every().day.at("00:00").do(run_once)
        print("Scheduler started (Ctrl-C to stop) …")
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        run_once()


if __name__ == "__main__":
    main()
