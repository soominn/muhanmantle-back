from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from gensim.models import KeyedVectors
from .models import AnswerWord, BaseWord
from django.db import IntegrityError
import json

# FastText 모델 로드
model = KeyedVectors.load_word2vec_format("cc.ko.300.vec", binary=False, unicode_errors="ignore")


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

        # 모든 후보 단어와의 유사도 계산
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

        # 유사도 내림차순 정렬
        similarities = sorted(similarities, key=lambda x: x["similarity_percentage"], reverse=True)

        # 상위 100개 단어만 추출
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

        # get_similarity_rank_list를 호출하여 순위 데이터 가져오기
        response = get_similarity_rank_list(request, id)
        if response.status_code != 200:
            return response

        data = json.loads(response.content)
        similarities = data.get("top_100_similarities", [])

        # 입력 단어가 BaseWord 테이블에 존재하는지 확인
        base_word_exists = BaseWord.objects.filter(base_word=input_word).exists()

        # 입력 단어가 순위 리스트에 있는지 확인
        rank = "?"
        for item in similarities:
            if item["word"] == input_word:
                rank = item["rank"] if item["rank"] <= 100 else "순위 밖"
                break

        # 순위 리스트에 없지만 BaseWord에 존재하면 순위 밖 처리
        if rank == "?" and base_word_exists:
            rank = "순위 밖"

        # 모델에 단어 존재 여부 확인
        if input_word not in model.key_to_index:
            return JsonResponse({"error": f"Input word '{input_word}' not found in the model."}, status=400)
        if answer.answer_word not in model.key_to_index:
            return JsonResponse({"error": f"Answer word '{answer.answer_word}' not found in the model."}, status=400)

        # 입력 단어와 정답 단어의 유사도 계산
        similarity_score = model.similarity(input_word, answer.answer_word)

        # 유사도를 %로 변환
        similarity_percentage = max(0, min(similarity_score * 100, 100))

        # 유사도가 100%일 경우 rank를 "정답!"으로 설정
        if similarity_percentage == 100:
            rank = "정답!"

        # BaseWord에 입력 단어가 없으면 추가
        if not base_word_exists:
            try:
                new_base_word = BaseWord(base_word=input_word)
                new_base_word.save()
            except IntegrityError:
                pass  # 이미 존재하는 단어라면 무시

        return JsonResponse({
            "id": id,
            "answer_word": answer.answer_word,
            "input_word": input_word,
            "similarity_percentage": round(similarity_percentage, 2),
            "rank": rank
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)