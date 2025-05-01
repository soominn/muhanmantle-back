# 🧠 무한맨틀 백엔드 (Muhanmantle Backend)

**한국어 단어 유사도 기반 싱글 플레이 게임 - 백엔드 서버**

FastText 모델을 활용한 단어 유사도 계산 API를 제공하며,  
Django 기반의 REST API 서버로 구성되어 있습니다.  
React 프론트엔드와 연동되어 실제 배포 및 운영 중입니다.

🔗 [서비스 바로가기](https://www.muhanmantle.com)  
🔧 [프론트엔드 GitHub](https://github.com/soominn/muhanmantle-front)

---

## 📌 프로젝트 개요

- 한국어 단어 간 의미 유사도를 기반으로 정답을 맞히는 싱글 플레이 게임
- FastText 임베딩 모델을 활용하여 유사도 계산
- Django REST Framework로 API 구성
- AWS Lightsail + Nginx + HTTPS 기반 배포

---

## 🛠 기술 스택

| 분류        | 기술 |
|-------------|------|
| 언어        | Python |
| 프레임워크  | Django, Django REST Framework |
| AI 모델     | FastText (Pre-trained Word Embedding) |
| DB          | MariaDB |
| 서버 & 배포 | AWS Lightsail, Nginx, Let's Encrypt, Route 53 |
| 기타 도구   | Git, GitHub, Postman, django-cors-headers |

---

## 🚀 주요 기능

- 🔎 **FastText 유사도 계산 API**
  - 사용자 입력 단어와 정답 단어 간 의미 유사도(%) 계산 반환

- 🧠 **정답 단어 랜덤 출제**
  - 일정 조건을 만족하는 단어를 정답으로 무작위 출제

- 🧾 **입력 단어 기록 API**
  - 사용자 입력 기록을 MariaDB에 저장 및 조회 가능하도록 구현

- 🔐 **CORS 정책 대응 및 프론트 통신**
  - django-cors-headers 설정으로 React와의 원활한 연동 지원

---

## 🖥️ 배포 환경

- **AWS Lightsail**: Ubuntu 서버 환경 구축
- **Nginx + Gunicorn**: WSGI 서버 구성
- **Let's Encrypt**: HTTPS 인증서 적용
- **Route 53**: 도메인 연결 및 DNS 설정
- **환경 변수 관리**: `.env` 파일 및 settings 분리

---

## 🧩 트러블슈팅 & 개선 사항

| 문제 | 해결 방법 |
|------|------------|
| FastText 모델 로딩 지연 | Lazy loading + 캐싱 처리로 응답 속도 개선 |
| CORS 오류 발생 | `django-cors-headers` 설정 적용 |
| HTTPS 요청 시 포워딩 오류 | Nginx proxy 설정 + Django `SECURE_*` 설정 조정 |

---

## 📂 디렉토리 구조

```bash
muhanmantle-backend/
├── config/                    # Django 프로젝트 설정 모듈
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py            # 전역 설정 파일
│   ├── urls.py                # 루트 URLConf
│   ├── utils.py               # 공통 유틸 함수
│   └── wsgi.py
│
├── simword/                   # FastText 유사도 계산 및 게임 로직 앱
│   ├── migrations/            # DB 마이그레이션 파일
│   │   ├── __init__.py
│   │   └── 0001_initial.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py              # 입력 기록 모델 정의
│   ├── news_word_analysis.py  # 뉴스 기반 단어 추출 로직
│   ├── tests.py
│   ├── urls.py                # 앱 단위 URLConf
│   ├── views.py               # API 뷰 로직
│   └── word_scraper.py        # 단어 수집 크롤러
│
├── manage.py                  # Django 명령어 실행 스크립트
└── .gitignore                 # Git 추적 제외 파일 목록
```

---

## 📈 향후 개선 예정

- **로그인 기반 유저 세션** 및 게임 플레이 통계 저장 기능 추가
- **랭킹 시스템 구현**으로 사용자 경쟁 요소 도입
- FastText **도메인 특화 모델 재학습**을 통한 유사도 정확도 향상

---

## 🙋‍♀️ 개발자 정보

**👩‍💻 백엔드 개발**: 조수민 (Soomin Cho)  
- GitHub: [@soominn](https://github.com/soominn)  
- Blog: [som-ethi-ng.tistory.com](https://som-ethi-ng.tistory.com)


