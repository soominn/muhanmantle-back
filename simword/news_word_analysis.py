import requests
from bs4 import BeautifulSoup
from collections import Counter
from konlpy.tag import Okt
import time
import os
import django
import schedule


def setup_django_environment():
    """Django 환경을 설정합니다."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # 정확한 경로 설정
    django.setup()


setup_django_environment()


from simword.models import BaseWord


def get_popular_articles():
    """
    네이버 뉴스 인기 기사 페이지에서 최대 50개의 기사를 수집합니다.
    """
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    articles = []
    visited_urls = set()  # 중복 링크 확인용 집합

    try:
        print(f"요청 URL: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"페이지 로드 실패: {e}")
        return articles

    soup = BeautifulSoup(response.text, "html.parser")
    news_links = soup.select("div.rankingnews_box a.list_title[href]")  # 인기 기사 링크 선택자

    for link in news_links:
        article_url = link["href"]
        if not article_url.startswith("http"):
            article_url = "https://news.naver.com" + article_url

        # 중복 링크 확인 및 건너뛰기
        if article_url in visited_urls:
            continue

        visited_urls.add(article_url)  # 고유 링크 추가

        try:
            print("article_url : " + article_url)
            article_response = requests.get(article_url, headers=headers)
            article_response.raise_for_status()
        except requests.RequestException as e:
            print(f"기사 로드 실패: {e}")
            continue

        article_soup = BeautifulSoup(article_response.text, "html.parser")
        content = article_soup.select_one("#dic_area")

        if content:
            article_text = content.get_text(strip=True)
            if article_text not in articles:  # 중복된 기사 내용 확인
                articles.append(article_text)

        # 최대 50개의 기사만 수집
        if len(articles) >= 50:
            break

        # 요청 간격 유지
        time.sleep(1)

    return articles


def extract_frequent_words(texts):
    """
    수집한 텍스트에서 빈도수가 높은 단어를 추출합니다.
    """
    okt = Okt()
    all_words = []

    for text in texts:
        nouns = okt.nouns(text)  # 명사 추출
        filtered_nouns = [noun for noun in nouns if len(noun) > 1]  # 한 글자 단어 제외
        all_words.extend(filtered_nouns)

    # 단어 빈도 계산
    word_counts = Counter(all_words)

    # 상위 50개 단어 반환
    return word_counts.most_common(50)


def save_words_to_baseword(words):
    """
    상위 50개의 단어를 BaseWord 모델에 저장합니다.
    """
    for word, count in words:
        BaseWord.objects.get_or_create(base_word=word)
    print("크롤링한 단어를 BaseWord 모델에 저장했습니다.")


def main():
    print("네이버 뉴스 인기 기사에서 데이터를 수집 중입니다...")
    articles = get_popular_articles()

    if not articles:
        print("기사를 가져오지 못했습니다.")
        return

    print(f"총 {len(articles)}개의 기사를 분석합니다.")
    frequent_words = extract_frequent_words(articles)

    # 단어 순위 출력
    print("\n단어 순위 리스트 (TOP 50):")
    for rank, (word, count) in enumerate(frequent_words, start=1):
        print(f"{rank}. {word} ({count}회)")

    save_words_to_baseword(frequent_words)


# 스케줄링 설정
schedule.every().day.at("00:00").do(main)  # 매일 자정에 실행


if __name__ == "__main__":
    print("스케줄러 실행 중... (Ctrl+C로 종료)")
    while True:
        schedule.run_pending()
        time.sleep(1)
