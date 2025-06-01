import os
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from gensim.models import KeyedVectors
from .models import AnswerWord, BaseWord
from django.db import IntegrityError
import json
from django.conf import settings

# 모델 파일 경로
VEC_FILE = os.path.join(settings.BASE_DIR, 'cc.ko.300.vec')
KV_FILE = os.path.join(settings.BASE_DIR, 'cc.ko.300.kv')

# 전역 모델 변수 (한 번만 로드 후 계속 사용)
model = None

def load_model():
    """FastText 모델을 로드하고 전역 변수로 저장"""
    global model

    if os.path.exists(KV_FILE):
        model = KeyedVectors.load(KV_FILE)
    else:
        # 원본 벡터 파일 로드
        model = KeyedVectors.load_word2vec_format(VEC_FILE, binary=False, unicode_errors="ignore")

        # 벡터를 float16으로 변환 (메모리 절약)
        model.vectors = model.vectors.astype("float16")

        # 변환된 모델을 저장
        model.save(KV_FILE)

# 🚀 서버 시작 시 모델을 한 번 로드
load_model()

def answer_word_count(request):
    """전체 AnswerWord 개수를 반환"""
    total_count = AnswerWord.objects.all().count()
    return JsonResponse({"total_count": total_count})

def get_similarity_rank_list(request, id):
    """특정 AnswerWord와 BaseWord 간 유사도 랭킹 상위 100개를 반환"""
    try:
        answer = get_object_or_404(AnswerWord, pk=id)
        candidate_words = list(BaseWord.objects.values_list("base_word", flat=True))

        if not candidate_words:
            return JsonResponse({"error": "No candidate words found in the database."}, status=404)

        if answer.answer_word not in model.key_to_index:
            return JsonResponse({"error": f"Answer word '{answer.answer_word}' not found in the model."}, status=400)

        similarities = [
            {
                "word": word,
                "similarity_percentage": round(float(model.similarity(answer.answer_word, word)) * 100, 2)
            }
            for word in candidate_words
            if word in model.key_to_index and word != answer.answer_word
        ]

        if not similarities:
            return JsonResponse({"error": "No valid candidate words found for similarity calculation."}, status=404)

        similarities = sorted(similarities, key=lambda x: x["similarity_percentage"], reverse=True)

        top_similarities = [
            {"word": item["word"], "similarity_percentage": item["similarity_percentage"], "rank": rank + 1}
            for rank, item in enumerate(similarities[:100])
        ]

        return JsonResponse({
            "id": id,
            "answer_word": answer.answer_word,
            "top_100_similarities": top_similarities
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def calculate_similarity(request, id, input_word):
    """입력 단어와 정답 단어의 유사도를 계산하고, 랭킹을 반환"""
    try:
        answer = get_object_or_404(AnswerWord, pk=id)

        response = get_similarity_rank_list(request, id)
        if response.status_code != 200:
            return response

        data = json.loads(response.content)
        similarities = data.get("top_100_similarities", [])

        base_word_exists = BaseWord.objects.filter(base_word=input_word).exists()

        rank = "?"
        for item in similarities:
            if item["word"] == input_word:
                rank = item["rank"] if item["rank"] <= 100 else "순위 밖"
                break

        if rank == "?" and base_word_exists:
            rank = "순위 밖"

        if input_word not in model.key_to_index:
            return JsonResponse({"error": f"Input word '{input_word}' not found in the model."}, status=400)
        if answer.answer_word not in model.key_to_index:
            return JsonResponse({"error": f"Answer word '{answer.answer_word}' not found in the model."}, status=400)

        similarity_score = model.similarity(input_word, answer.answer_word)
        similarity_percentage = round(similarity_score * 100, 2)

        if similarity_percentage == 100:
            rank = "정답!"

        if not base_word_exists:
            try:
                new_base_word = BaseWord(base_word=input_word)
                new_base_word.save()
            except IntegrityError:
                pass

        return JsonResponse({
            "id": id,
            "input_word": input_word,
            "similarity_percentage": similarity_percentage,
            "rank": rank
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)