# 무한맨틀 백엔드 (Muhanmantle Backend)

한국어 단어 유사도 기반 싱글 플레이 게임의 백엔드 API 서버.

[서비스](https://www.muhanmantle.com) | [프론트엔드](https://github.com/soominn/muhanmantle-front)

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 프레임워크 | FastAPI |
| ORM / 마이그레이션 | SQLAlchemy 2.0, Alembic |
| AI 모델 | FastText KeyedVectors (gensim) |
| DB | MariaDB |
| 서버 | Uvicorn / Gunicorn |

---

## 프로젝트 구조

```
muhanmantle-back/
├── models/                          # 대용량 ML 파일 (Git 제외, README만 추적)
│   ├── README.md
│   ├── fasttext/                    # cc.ko.300.vec / .kv
│   └── embedding-cache/             # sentence-transformer BaseWord 캐시
├── app/
│   ├── main.py                      # FastAPI 앱, lifespan, 미들웨어
│   ├── api/
│   │   └── v1/
│   │       ├── router.py            # 라우터 집계
│   │       └── endpoints/
│   │           ├── health.py        # GET /health
│   │           └── game.py          # /api/game/session …
│   ├── core/
│   │   ├── config.py                # pydantic-settings (.env 로드)
│   │   └── cors.py                  # CORS 미들웨어 설정
│   ├── db/
│   │   ├── base.py                  # DeclarativeBase
│   │   └── session.py               # 엔진, SessionLocal, get_db
│   ├── models/
│   │   ├── answer_word.py
│   │   ├── base_word.py
│   │   ├── game_session.py
│   │   └── base_word_candidate.py
│   ├── schemas/
│   │   └── simword.py
│   ├── services/
│   │   ├── game_session_service.py
│   │   ├── model_loader.py
│   │   └── similarity_service.py
│   └── repositories/
│       ├── simword_repository.py
│       └── game_session_repository.py
├── alembic/versions/              # 0001–0003
├── scripts/
│   ├── download_wordlists.py
│   ├── seed_words.py
│   ├── word_scraper.py
│   └── news_word_analysis.py
├── tests/
│   ├── test_health.py
│   ├── test_game_session.py
│   └── test_stdict_openapi.py
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## 로컬 개발 환경 설정

### 1. 의존성 설치

```bash
cd muhanmantle-back
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경 변수

```bash
cp .env.example .env
# DATABASE_URL 수정
```

기존 django-environ 형식(`mysql://...`)도 자동 변환됩니다.

### 2b. FastText 모델 파일

기본 경로는 `models/fasttext/cc.ko.300.vec` 및 `cc.ko.300.kv` 입니다.  
받아 둔 파일을 그 위치로 옮기거나, `.env`의 `VEC_FILE` / `KV_FILE`로 지정하세요. 자세한 내용은 `models/README.md` 참고.

### 3. DB 마이그레이션

**신규 설치:**
```bash
alembic upgrade head
```

**기존 Django DB (테이블명 동일 — 데이터 변환 불필요):**
```bash
alembic stamp 0001
```

### 4. 개발 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API 명세

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 헬스 체크 → `{"status": "ok"}` |
| `GET` | `/api/game/session` | 세션 조회/없으면 생성 (Set-Cookie). `revealed_answer`는 포기 전 `null` |
| `POST` | `/api/game/session/guess` | 입력 단어 제출 + 유사도/순위 계산. 정답 단어는 넣지 않음 |
| `POST` | `/api/game/session/reset` | 다음 문제로 초기화 (포기 공개도 해제) |
| `POST` | `/api/game/session/give-up` | 현재 퍼즐 포기. public_state + `revealed_answer` |
| `GET` | `/api/game/session/shout-ranking` | 같은 정답에 대한 추측 단어 순위 |

### 포기 / 외침 순위

`POST /api/game/session/give-up` 응답은 기존 세션 필드와 `revealed_answer`다.

```json
{ "number": 12, "word": "사과" }
```

`number`는 화면에 이미 보이는 N번째 정답의 N이며, 프론트가 쓰는 `answer_id`와 같다. 포기 전에는 `revealed_answer`가 `null`이고 guess 응답에는 정답 단어를 넣지 않는다. 포기 후에는 세션에 남아 새로고침(`GET /api/game/session`)에도 같은 공개가 유지된다.

`GET /api/game/session/shout-ranking`은 현재 세션의 정답 기준으로, 세션들이 제출한 단어를 집계한다. 같은 세션의 같은 단어는 한 번만 센다. 응답은 `{"items": [{"word": "...", "count": 3}]}`이고 `count` 내림차순, 상위 20개다. 정답 단어를 제출한 세션이 있으면 순위에 포함하지만 정답이라고 표시하지는 않는다.

에러 응답: `{"error": "..."}` (프론트엔드 호환)

### rank 필드

| 값 | 의미 |
|----|------|
| `1`–`500` (int) | BaseWord 중 순위 |
| `"순위 밖"` | 500위 밖 |
| `"?"` | 신규 입력 단어 (BaseWord 신규 후보) |
| `"정답!"` | 정답과 일치 또는 유사도 100% |

---

## 테스트

```bash
pytest -v
```

SQLite 인메모리 DB + 모의 모델 사용 — MariaDB나 실제 모델 파일 불필요.

---

## 프로덕션 배포

### Gunicorn + uvicorn

```bash
gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

> 워커당 FastText 모델 ~3 GB 로드. 2워커 기준 ~6 GB RAM 필요.

### Nginx

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 60s;
}
location /health { proxy_pass http://127.0.0.1:8000; }
```

---

## 유틸리티 스크립트

```bash
# 위키낱말사전에서 단어 수집 → AnswerWord + BaseWord 시딩 (레거시)
python scripts/word_scraper.py

# 권장: 국어원·KoFREN·ko_50k 기반 시딩 (원본은 muhanmantle-etc/wordlists/)
python scripts/download_wordlists.py   # 최초 1회 다운로드
python scripts/seed_words.py

# 네이버 뉴스 명사 수집 → BaseWord 추가 (konlpy 필요)
python scripts/news_word_analysis.py            # 1회 실행
python scripts/news_word_analysis.py --loop     # 매일 자정 반복

# BaseWord 검증: 표준국어대사전 Open API (batch 30,000)
python -m scripts.baseword_dictionary_audit --batch-index 0 --batch-size 30000
python -m scripts.baseword_dictionary_audit --batch-index 1 --batch-size 30000
```

---

## 개발자 정보

**백엔드**: 조수민 (Soomin Cho)
- GitHub: [@soominn](https://github.com/soominn)
