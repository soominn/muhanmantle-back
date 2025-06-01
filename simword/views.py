import os
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from gensim.models import KeyedVectors
from .models import AnswerWord, BaseWord
from django.db import IntegrityError
import json
from django.conf import settings
import threading
import time
import random

# 모델 파일 경로
VEC_FILE = os.path.join(settings.BASE_DIR, 'cc.ko.300.vec')
KV_FILE = os.path.join(settings.BASE_DIR, 'cc.ko.300.kv')

# 전역 모델 변수 (한 번만 로드 후 계속 사용)
model = None
_model_lock = threading.Lock()  # 스레드 안전성을 위한 락


class PowerfulMemoryKeeper:
    def __init__(self, model):
        self.model = model
        self.is_running = True
        self.access_count = 0
        self._lock = threading.Lock()

    def intensive_memory_access(self):
        """메모리 전체 영역을 지속적으로 터치 (최적화됨)"""
        while self.is_running:
            try:
                with self._lock:  # 스레드 안전성
                    # 1. 벡터 배열 전체를 최적화된 방식으로 접근
                    if hasattr(self.model, 'vectors') and self.model.vectors is not None:
                        total_vectors = len(self.model.vectors)
                        chunk_size = min(500, total_vectors // 20)  # 더 작은 청크로 메모리 효율성 향상

                        for i in range(0, total_vectors, chunk_size):
                            end_idx = min(i + chunk_size, total_vectors)

                            # 메모리 효율적인 접근 방식
                            for j in range(i, end_idx, 10):  # 10개씩 건너뛰며 샘플링
                                if j < total_vectors:
                                    _ = self.model.vectors[j].sum()  # 개별 벡터 합계

                            time.sleep(0.005)  # 5ms로 단축

                    # 2. 키 인덱스 딕셔너리 접근
                    if hasattr(self.model, 'key_to_index'):
                        keys = list(self.model.key_to_index.keys())
                        sample_keys = random.sample(keys, min(50, len(keys)))  # 50개로 줄임

                        for key in sample_keys:
                            _ = self.model.key_to_index[key]

                    # 3. 실제 유사도 계산 수행
                    self.perform_dummy_calculations()

                self.access_count += 1
                if self.access_count % 10 == 0:  # 10번마다 한번씩만 출력
                    print(f"메모리 유지 작업 #{self.access_count} 완료")

            except Exception as e:
                print(f"메모리 유지 에러: {e}")

            # 12초마다 실행 (좀 더 자주)
            time.sleep(12)

    def perform_dummy_calculations(self):
        """실제 모델 연산 수행으로 계산 엔진도 활성화"""
        try:
            keys = list(self.model.key_to_index.keys())
            if len(keys) >= 4:  # 4개 단어로 더 다양한 연산
                sample_words = random.sample(keys, 4)

                # 다양한 연산 수행
                _ = self.model.similarity(sample_words[0], sample_words[1])
                _ = self.model.similarity(sample_words[2], sample_words[3])

                # 벡터 직접 접근
                for word in sample_words[:2]:
                    _ = self.model[word]

        except Exception as e:
            print(f"더미 계산 에러: {e}")

    def start_background_keeper(self):
        """백그라운드에서 메모리 유지 시작"""
        keeper_thread = threading.Thread(target=self.intensive_memory_access, daemon=True)
        keeper_thread.start()
        print("🚀 강력한 메모리 키퍼 시작!")
        return keeper_thread

    def stop(self):
        """메모리 키퍼 중지"""
        self.is_running = False


# 전역 메모리 키퍼 변수
memory_keeper = None


def load_model():
    """FastText 모델을 로드하고 전역 변수로 저장"""
    global model, memory_keeper

    with _model_lock:  # 스레드 안전성
        if model is not None:  # 이미 로드된 경우 중복 방지
            return

        if os.path.exists(KV_FILE):
            print("기존 KV 파일 로드 중...")
            model = KeyedVectors.load(KV_FILE)
        else:
            print("원본 벡터 파일 로드 및 변환 중...")
            # 원본 벡터 파일 로드
            model = KeyedVectors.load_word2vec_format(VEC_FILE, binary=False, unicode_errors="ignore")

            # 벡터를 float16으로 변환 (메모리 절약)
            model.vectors = model.vectors.astype("float16")

            # 변환된 모델을 저장
            model.save(KV_FILE)
            print("KV 파일 저장 완료")

        # 🚀 PowerfulMemoryKeeper만 사용 (keep_model_warm_improved 제거)
        memory_keeper = PowerfulMemoryKeeper(model)
        memory_keeper.start_background_keeper()

        print(f"모델 로드 완료! 어휘 크기: {len(model.key_to_index):,}개")


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


# 추가 유틸리티 함수들
def get_memory_keeper_status(request):
    """메모리 키퍼 상태 확인"""
    global memory_keeper
    if memory_keeper:
        return JsonResponse({
            "status": "running" if memory_keeper.is_running else "stopped",
            "access_count": memory_keeper.access_count,
            "model_vocab_size": len(model.key_to_index) if model else 0
        })
    return JsonResponse({"status": "not_initialized"})


def stop_memory_keeper(request):
    """메모리 키퍼 중지 (필요시)"""
    global memory_keeper
    if memory_keeper:
        memory_keeper.stop()
        return JsonResponse({"message": "메모리 키퍼가 중지되었습니다."})
    return JsonResponse({"message": "메모리 키퍼가 초기화되지 않았습니다."})


def restart_memory_keeper(request):
    """메모리 키퍼 재시작"""
    global memory_keeper
    if memory_keeper:
        memory_keeper.stop()
        time.sleep(1)

    if model:
        memory_keeper = PowerfulMemoryKeeper(model)
        memory_keeper.start_background_keeper()
        return JsonResponse({"message": "메모리 키퍼가 재시작되었습니다."})
    return JsonResponse({"message": "모델이 로드되지 않았습니다."})