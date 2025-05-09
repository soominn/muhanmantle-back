import threading
import time

def keep_model_warm(model, words=None, interval=600):
    # 기본 단어 목록 설정 (None일 경우)
    if words is None:
        words = ["안녕", "세상", "빠른", "텍스트", "한국", "인공지능", "기억"]

    # 모델을 주기적으로 접근하는 내부 함수
    def loop():
        while True:
            try:
                # 단어 리스트를 순회하면서 벡터를 가져와 메모리에 접근
                for word in words:
                    _ = model.get_vector(word)
            except Exception as e:
                # 에러 발생 시 출력
                print("keep_model_warm 에러:", e)
            # 지정한 시간(초)만큼 대기 후 다시 반복
            time.sleep(interval)

    # 위 루프를 백그라운드 스레드로 실행 (프로그램 종료 시 자동 종료됨)
    threading.Thread(target=loop, daemon=True).start()
