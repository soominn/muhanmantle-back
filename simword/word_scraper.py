import os
import django
import requests
from bs4 import BeautifulSoup
from gensim.models import KeyedVectors


def setup_django_environment():
    """Django 환경을 설정합니다."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


setup_django_environment()


from simword.models import AnswerWord, BaseWord


# FastText 모델 로드
print("FastText 모델을 로드 중...")
model = KeyedVectors.load_word2vec_format("../cc.ko.300.vec", binary=False, unicode_errors="ignore")
print("FastText 모델 로드 완료.")


def fetch_words_from_wiktionary(url):
    """
    위키낱말사전에서 자주 사용되는 한국어 단어를 가져옵니다.

    Args:
        url (str): 단어를 가져올 위키낱말사전 URL

    Returns:
        list: 중복 제거된 단어 목록
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"페이지 요청 실패: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    word_elements = soup.select("table.prettytable tbody tr td dl dd a")
    words = {word.get_text().strip() for word in word_elements if len(word.get_text().strip()) > 1}

    if not words:
        print("단어를 찾을 수 없습니다.")
        return []

    return list(words)  # 중복 제거 후 리스트로 반환


def filter_existing_words_in_fasttext(words):
    """
    FastText 모델에 존재하는 단어만 필터링합니다.

    Args:
        words (list): 필터링할 단어 목록

    Returns:
        list: FastText 모델에 존재하는 단어 목록
    """
    return [word for word in words if word in model.key_to_index]


def get_existing_words(model, words, field_name):
    """
    데이터베이스에 이미 저장된 단어를 가져옵니다.

    Args:
        model (Model): 확인할 모델 (AnswerWord 또는 BaseWord)
        words (list): 확인할 단어 목록
        field_name (str): 모델의 단어 필드 이름 (예: 'answer_word', 'base_word')

    Returns:
        set: 데이터베이스에 존재하는 단어의 집합
    """
    if not words:
        return set()

    return set(model.objects.filter(**{f"{field_name}__in": words}).values_list(field_name, flat=True))


def save_new_words_to_database(words, model, field_name):
    """
    새로운 단어를 데이터베이스에 저장합니다. (FastText 모델에 존재하는 단어만 저장)

    Args:
        words (list): 저장할 단어 목록
        model (Model): 저장할 모델 (AnswerWord 또는 BaseWord)
        field_name (str): 모델의 단어 필드 이름 (예: 'answer_word', 'base_word')
    """
    if not words:
        print(f"{model.__name__} 모델에 저장할 단어가 없습니다.")
        return

    # FastText에 존재하는 단어만 필터링
    words = filter_existing_words_in_fasttext(words)

    if not words:
        print(f"{model.__name__} 모델에 저장할 FastText 내 단어가 없습니다.")
        return

    existing_words = get_existing_words(model, words, field_name)
    new_words = [word for word in words if word not in existing_words]

    if new_words:
        model.objects.bulk_create([model(**{field_name: word}) for word in new_words])
        print(f"{len(new_words)}개의 새로운 단어를 {model.__name__} 모델에 저장했습니다.")
    else:
        print(f"{model.__name__} 모델에 저장할 새로운 단어가 없습니다.")


def main():
    """프로그램의 진입점입니다."""
    url = "https://ko.wiktionary.org/wiki/%EB%B6%80%EB%A1%9D:%EC%9E%90%EC%A3%BC_%EC%93%B0%EC%9D%B4%EB%8A%94_%ED%95%9C%EA%B5%AD%EC%96%B4_%EB%82%B1%EB%A7%90_5800"
    words = fetch_words_from_wiktionary(url)

    if words:
        save_new_words_to_database(words, AnswerWord, "answer_word")
        save_new_words_to_database(words, BaseWord, "base_word")


if __name__ == "__main__":
    main()
