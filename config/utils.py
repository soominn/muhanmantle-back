# config/utils.py

import threading
import time

def keep_model_warm(model, word="hello", interval=600):
    """
    일정 간격으로 모델에 접근하여 메모리에서 스왑되지 않도록 유지하는 함수.

    :param model: fastText 모델 객체
    :param word: 접근할 단어 (기본: "hello")
    :param interval: 접근 주기 (초, 기본: 600초 = 10분)
    """
    def loop():
        while True:
            try:
                _ = model.get_word_vector(word)
            except Exception as e:
                print("keep_model_warm error:", e)
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()
