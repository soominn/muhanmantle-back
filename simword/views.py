import os
import threading
import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from gensim.models import KeyedVectors
from .models import AnswerWord, BaseWord

# =========================
# 모델 로딩 (한 번만)
# =========================
VEC_FILE = os.path.join(settings.BASE_DIR, "cc.ko.300.vec")
KV_FILE  = os.path.join(settings.BASE_DIR, "cc.ko.300.kv")

model = None

def load_model():
    """FastText 모델 로드: kv가 있으면 그걸, 없으면 vec를 읽고 kv로 변환"""
    global model
    if os.path.exists(KV_FILE):
        model = KeyedVectors.load(KV_FILE)
    else:
        model = KeyedVectors.load_word2vec_format(VEC_FILE, binary=False, unicode_errors="ignore")
        model.save(KV_FILE)

# 서버 시작 시 1회 로드
load_model()

# =========================
# BaseWord 전역 캐시
# =========================
_BASE_WORDS = None
_BASE_VECS  = None
_BASE_DIRTY = True
_BASE_LOCK  = threading.RLock()

def _build_baseword_matrix(force: bool = False):
    """DB의 BaseWord를 읽어 전역 캐시(_BASE_WORDS, _BASE_VECS)를 구성"""
    global _BASE_WORDS, _BASE_VECS, _BASE_DIRTY

    with _BASE_LOCK:
        if not force and not _BASE_DIRTY and _BASE_WORDS is not None and _BASE_VECS is not None:
            return

        words = list(BaseWord.objects.values_list("base_word", flat=True))
        in_vocab = [w for w in words if w in model.key_to_index]

        if not in_vocab:
            _BASE_WORDS = []
            _BASE_VECS  = None
            _BASE_DIRTY = False
            return

        vecs = np.vstack([model.get_vector(w) for w in in_vocab]).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        vecs = vecs / norms

        _BASE_WORDS = in_vocab
        _BASE_VECS  = vecs
        _BASE_DIRTY = False

def _mark_baseword_dirty():
    """BaseWord 변경 시 호출(신규 추가/삭제 등)"""
    global _BASE_DIRTY
    with _BASE_LOCK:
        _BASE_DIRTY = True

def _ensure_cache_built():
    """필요 시 캐시 빌드"""
    _build_baseword_matrix()

def _answer_vector(answer_word: str) -> np.ndarray | None:
    """정답 단어 벡터를 L2 정규화하여 반환(float32)"""
    if answer_word not in model.key_to_index:
        return None
    v = model.get_vector(answer_word).astype(np.float32)
    v /= (np.linalg.norm(v) + 1e-12)
    return v

def _topk_from_sims(sims: np.ndarray, words: list[str], k: int = 500, exclude_word: str | None = None):
    """
    sims: shape (N,), words와 index 정렬 일치
    exclude_word: 자기 자신을 결과에서 제외하려고 할 때 사용
    return: [{"word": str, "similarity_percentage": float, "rank": int}, ...]
    """
    if sims.size == 0:
        return []

    k_eff = min(k + 1, sims.shape[0])
    idx = np.argpartition(-sims, kth=k_eff - 1)[:k_eff]
    idx = idx[np.argsort(-sims[idx])]

    top = []
    rank = 1
    for i in idx:
        w = words[i]
        if exclude_word is not None and w == exclude_word:
            continue
        top.append({
            "word": w,
            "similarity_percentage": round(float(sims[i]) * 100, 2),
            "rank": rank
        })
        rank += 1
        if len(top) == k:
            break
    return top

def _all_sims(answer_word: str):
    """
    answer_word 에 대한 전체 코사인 유사도 벡터를 반환.
    returns: (words(list[str]), sims(np.ndarray shape (N,)))
    """
    _ensure_cache_built()
    if _BASE_VECS is None or len(_BASE_WORDS) == 0:
        return [], None

    ans_vec = _answer_vector(answer_word)
    if ans_vec is None:
        return [], None

    sims = _BASE_VECS @ ans_vec
    return _BASE_WORDS, sims

# =========================
# API
# =========================
def answer_word_count(request):
    """전체 AnswerWord 개수를 반환"""
    total_count = AnswerWord.objects.all().count()
    return JsonResponse({"total_count": total_count})

def get_similarity_rank_list(request, id):
    """특정 AnswerWord와 BaseWord 간 유사도 랭킹 상위 500개(가속화 버전)"""
    try:
        answer = get_object_or_404(AnswerWord, pk=id)
        answer_word = answer.answer_word

        words, sims = _all_sims(answer_word)
        if sims is None or len(words) == 0:
            return JsonResponse({"error": "No valid candidate words found in the database/model."}, status=404)

        top_500 = _topk_from_sims(sims, words, k=500, exclude_word=answer_word)
        if not top_500:
            return JsonResponse({"error": "No valid candidate words found for similarity calculation."}, status=404)

        return JsonResponse({
            "id": id,
            "answer_word": answer_word,
            "top_500_similarities": top_500
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def calculate_similarity(request, id, input_word):
    """
    입력 단어와 정답 단어의 유사도를 계산하고, 랭킹을 반환.
    - 한 번의 전체 내적으로 유사도/순위를 함께 계산
    - input_word가 BaseWord에 없으면 추가하고 캐시 dirty 처리(다음 요청 시 반영)
    """
    try:
        answer = get_object_or_404(AnswerWord, pk=id)
        answer_word = answer.answer_word

        # 전체 유사도 계산
        words, sims = _all_sims(answer_word)
        if sims is None or len(words) == 0:
            return JsonResponse({"error": "No valid candidate words found in the database/model."}, status=404)

        # 모델 존재 여부 체크
        if input_word not in model.key_to_index:
            return JsonResponse({"error": f"Input word '{input_word}' not found in the model."}, status=400)
        if answer_word not in model.key_to_index:
            return JsonResponse({"error": f"Answer word '{answer_word}' not found in the model."}, status=400)

        # 입력/정답 벡터 정규화 후 유사도
        in_vec = model.get_vector(input_word).astype(np.float32)
        in_vec /= (np.linalg.norm(in_vec) + 1e-12)
        ans_vec = model.get_vector(answer_word).astype(np.float32)
        ans_vec /= (np.linalg.norm(ans_vec) + 1e-12)
        sim_input = float(in_vec @ ans_vec)
        similarity_percentage = round(sim_input * 100, 2)

        # 순위 계산 (정답 단어 제외)
        idx_map = {w: i for i, w in enumerate(words)}
        base_word_exists = input_word in idx_map

        rank = "순위 밖"
        if base_word_exists:
            i_input = idx_map[input_word]
            my_sim = sims[i_input]

            i_answer = idx_map.get(answer_word, None)
            greater = (sims > my_sim)
            if i_answer is not None:
                greater[i_answer] = False

            rank_val = int(greater.sum()) + 1
            rank = rank_val if rank_val <= 500 else "순위 밖"
        else:
            # BaseWord에 없으면 추가 & 다음 요청에서 캐시 재빌드
            try:
                BaseWord.objects.create(base_word=input_word)
                _mark_baseword_dirty()
            except IntegrityError:
                pass
            rank = "?"

        # 정답 처리
        if input_word == answer_word or similarity_percentage == 100:
            rank = "정답!"

        return JsonResponse({
            "id": id,
            "input_word": input_word,
            "similarity_percentage": similarity_percentage,
            "rank": rank
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
