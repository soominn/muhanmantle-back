import os
import django
import requests
from bs4 import BeautifulSoup
from gensim.models import KeyedVectors

# Django 환경 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from simword.models import AnswerWord, BaseWord

# 절대경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC_FILE = os.path.join(BASE_DIR, "cc.ko.300.vec")
KV_FILE = os.path.join(BASE_DIR, "cc.ko.300.kv")

# FastText 모델 로드 (메모리 절약)
def load_fasttext_model():
    if os.path.exists(KV_FILE):
        return KeyedVectors.load(KV_FILE)

    model = KeyedVectors.load_word2vec_format(VEC_FILE, binary=False, unicode_errors="ignore")
    model.vectors = model.vectors.astype("float16")  # 메모리 절약을 위해 float16 변환
    model.save(KV_FILE)
    return model

# FastText 모델 전역 변수로 로드 (한 번만 실행)
model = load_fasttext_model()

# 위키낱말사전에서 단어 가져오기
def fetch_words_from_wiktionary(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    word_elements = soup.select("table.prettytable tbody tr td dl dd a")
    return list({word.get_text().strip() for word in word_elements if len(word.get_text().strip()) > 1})

# FastText 모델에 존재하는 단어만 필터링
def filter_existing_words_in_fasttext(words):
    return [word for word in words if word in model.key_to_index]

# 데이터베이스에서 이미 저장된 단어 확인
def get_existing_words(model, words, field_name):
    if not words:
        return set()
    return set(model.objects.filter(**{f"{field_name}__in": words}).values_list(field_name, flat=True))

# 새로운 단어를 데이터베이스에 저장
def save_new_words_to_database(words, model, field_name):
    if not words:
        return

    words = filter_existing_words_in_fasttext(words)  # FastText 모델에 존재하는 단어만 저장
    if not words:
        return

    existing_words = get_existing_words(model, words, field_name)
    new_words = [word for word in words if word not in existing_words]

    if new_words:
        model.objects.bulk_create([model(**{field_name: word}) for word in new_words])

# 실행 메인 함수
def main():
    url = "https://ko.wiktionary.org/wiki/%EB%B6%80%EB%A1%9D:%EC%9E%90%EC%A3%BC_%EC%93%B0%EC%9D%B4%EB%8A%94_%ED%95%9C%EA%B5%AD%EC%96%B4_%EB%82%B1%EB%A7%90_5800"
    words = fetch_words_from_wiktionary(url)

    if words:
        save_new_words_to_database(words, AnswerWord, "answer_word")
        save_new_words_to_database(words, BaseWord, "base_word")

    print("실행이 완료되었습니다.")

if __name__ == "__main__":
    main()

