# 무한맨틀 백엔드 Podman 이전

API를 서버에 직접 깔아 `supervisor`로 띄우던 방식에서 Podman 컨테이너로 옮긴다. 공개 입구는 그대로 호스트 Nginx(TLS)다. Nginx가 `127.0.0.1:8000`으로 프록시하고, 컨테이너도 그 주소에만 붙는다.

## 선택한 구성

| 항목 | 값 |
|------|----|
| 이미지 | `Containerfile`, 태그 `localhost/muhanmantle-back:latest` |
| 실행 | `docker-compose.yml` 을 `podman compose` 또는 `podman-compose`로 |
| 네트워크 | **호스트 네트워크** (`network_mode: host`) |
| API 주소 | `127.0.0.1:8000` (`BIND_HOST` / `BIND_PORT`로 변경 가능, 기본값 유지) |
| DB | 호스트 MariaDB. `DATABASE_URL`의 호스트는 `127.0.0.1` |
| 모델 | 호스트 `./models` → 컨테이너 `/app/models` 볼륨. 이미지에 넣지 않음 |
| 설정 | 서버의 `~/projects/muhanmantle-back/.env` (Git에 없음) |
| 마이그레이션 | 컨테이너를 바꾸기 전에 새 이미지로 `alembic upgrade head` 를 한 번 실행 |
| 공지 | `notices/*.md` 는 저장소 파일이라 이미지에 포함된다. 볼륨이 아니다 |

호스트 네트워크를 쓰는 이유는 MariaDB와 Nginx가 이미 `127.0.0.1`에 있기 때문이다. 컨테이너가 호스트와 같은 네트워크 네임스페이스를 쓰면 `DATABASE_URL`의 `127.0.0.1:3306`이 호스트 MariaDB이고, `user@localhost` 권한도 그대로다. 프로세스는 `127.0.0.1:8000`에만 바인드하므로 공인 IP의 8000번으로는 열리지 않는다. Nginx 설정은 바꾸지 않아도 된다.

`host.containers.internal` 같은 브리지 주소는 호스트의 루프백(MariaDB가 보통 듣는 곳)에 닿지 않는다. 그래서 쓰지 않는다.

## 포트

이 배포가 호스트에서 새로 여는 포트는 `127.0.0.1:8000` 하나다. 이미 이 API가 쓰던 포트다.

| 포트 | 용도 |
|------|------|
| 80, 443 | 호스트 Nginx. 프론트 정적 파일과 API 프록시 |
| 127.0.0.1:8000 | 이 API. Nginx `proxy_pass` 대상 |
| 3306 | 호스트 MariaDB. 컨테이너가 포트를 추가로 열지 않음 |
| 127.0.0.1:3307 | 선택 사항. `compose.local-db.yml`의 개발용 MariaDB. 운영에서 켜지 않음 |

`soomin-hub`와 `url-link-cards`는 2026-10-07 기준으로 GitHub에서 공개 저장소로 열리지 않아(404) 그쪽 호스트 포트를 확인하지 못했다. 이 API는 새 포트를 잡지 않고 기존 8000을 유지한다. 프론트 컨테이너를 따로 띄울 때도 호스트의 `127.0.0.1:8000`은 이 API 전용으로 둔다.

## 서버에서 한 번만 할 일

아래는 SSH로 배포 계정에 들어간 뒤의 순서다. GitHub Actions 시크릿 이름(`SERVER_IP`, `SSH_USERNAME`, `SSH_PRIVATE_KEY`)은 바뀌지 않는다.

이 변경이 `main`에 들어가 워크플로가 돌기 **전에** 5번(supervisor 중지)까지 끝내야 한다. 예전 프로세스가 8000을 잡고 있으면 새 컨테이너가 뜨지 못하고 배포 잡이 실패한다.

### 1. Podman 설치

Ubuntu 예시:

```bash
sudo apt-get update
sudo apt-get install -y podman
podman compose version || sudo apt-get install -y podman-compose
```

`podman compose version`이 되면 내장 명령을 쓴다. 안 되면 `podman-compose` 패키지를 설치한다. 배포 스크립트는 둘 다 인식한다.

rootless(권장)로 SSH 사용자 계정에서 `podman info`가 되면 된다. Ubuntu 패키지는 보통 `/etc/subuid`, `/etc/subgid`를 만들어 준다.

```bash
podman info >/dev/null && echo ok
```

### 2. 저장소

```bash
cd ~/projects/muhanmantle-back
git pull origin main
```

### 3. 환경 파일

```bash
cp .env.example .env
chmod 600 .env
```

`.env`에 실제 `DATABASE_URL`을 넣는다. 호스트는 `127.0.0.1`, 포트는 `3306`이다.

```
DATABASE_URL=mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/muhanmantle
```

`BIND_HOST`는 `127.0.0.1`, `BIND_PORT`는 `8000`으로 둔다. `BIND_HOST=0.0.0.0`으로 바꾸면 호스트 네트워크 때문에 API가 공인 인터페이스에도 열린다.

예전에 `VEC_FILE` / `KV_FILE`을 호스트 절대 경로로 적어 두었다면 지운다. 컨테이너 안 기본 경로는 아래 4번의 마운트와 맞다. 호스트 경로는 컨테이너 안에 없다.

```
# 비워 두면 기본값 /app/models/fasttext/cc.ko.300.vec , cc.ko.300.kv
```

문장 임베딩 캐시를 쓸 때도 `EMBEDDING_CACHE_DIR`를 호스트 경로로 두지 않는다. 기본값 `/app/models/embedding-cache`가 같은 볼륨 안이다.

### 4. 모델 파일

대용량 파일은 이미지에 들어가지 않는다. 호스트의 `models/`를 `/app/models`에 마운트한다.

```bash
mkdir -p ~/projects/muhanmantle-back/models/fasttext
# 기존 파일을 이 디렉터리로 옮긴다. 자세한 배치는 models/README.md
ls -lh models/fasttext/cc.ko.300.vec models/fasttext/cc.ko.300.kv
```

`.kv`만 있어도 된다. `.vec`만 있으면 첫 기동 때 `.kv`를 같은 디렉터리에 만든다. 볼륨은 쓰기 가능해야 한다. 배포 계정이 이 디렉터리를 읽고 쓸 수 있어야 한다. rootless Podman에서는 그 계정이 `podman`을 실행한다.

### 5. 기존 supervisor 중지와 비활성화

프로그램 이름은 `muhanmantle`이다. 설정 파일은 보통 `/etc/supervisor/conf.d/muhanmantle.conf`이다. 파일을 지우지 말고 자동 시작만 끈다. 롤백할 때 다시 켠다.

```bash
sudo supervisorctl stop muhanmantle
```

설정에서 다음처럼 바꾼다.

```ini
autostart=false
autorestart=false
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

`muhanmantle`가 아직 떠 있으면 `sudo supervisorctl stop muhanmantle`를 다시 실행한다. 8000이 비었는지 확인한다.

```bash
ss -ltnp | grep ':8000' || echo "8000 is free"
```

### 6. 첫 기동

```bash
cd ~/projects/muhanmantle-back
podman compose build
podman run --rm --network host --env-file .env \
  --name muhanmantle-migrate \
  localhost/muhanmantle-back:latest \
  alembic upgrade head
podman compose up -d
```

`podman compose`가 없으면 같은 인자에 `podman-compose`를 쓴다.

FastText 로드는 수 분 걸린다. 워커 수 기본값은 2이고, 워커마다 모델을 올린다. 메모리가 부족하면 `.env`에 `WEB_CONCURRENCY=1`을 넣는다.

```bash
python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read())"
podman logs --tail 50 muhanmantle-api
```

`{"status": "ok"}`가 나오면 된다. 기존 Django DB를 아직 Alembic에 찍지 않았다면 예전과 같이 `alembic upgrade head` 대신 상태를 맞춰야 할 수 있다. 그 경우는 README의 `alembic stamp 0001` 설명을 따른다. 이미 supervisor 배포에서 `upgrade head`를 쓰고 있었다면 같은 명령이면 된다.

### 7. Nginx

프록시 대상이 `http://127.0.0.1:8000`이면 설정을 바꾸지 않는다. `BIND_PORT`를 바꾼 경우에만 `proxy_pass`를 맞추고 `sudo nginx -t && sudo systemctl reload nginx` 한다.

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 60s;
}
location /health { proxy_pass http://127.0.0.1:8000; }
```

## 이후 배포

`main`에 푸시되면 테스트 잡 통과 후 SSH로 다음을 한다.

1. `~/projects/muhanmantle-back`에서 `git pull origin main`
2. 이미지 빌드
3. 새 이미지로 `alembic upgrade head` (이름 `muhanmantle-migrate`, 끝나면 삭제)
4. `muhanmantle-api` 재생성
5. 컨테이너가 running이고 `http://127.0.0.1:$BIND_PORT/health`가 응답할 때까지 최대 약 10분 대기. 실패하면 잡이 실패하고 로그 끝을 출력한다

모델이 크면 헬스 체크까지 시간이 걸린다. 앱이 뜨기 전에는 `/health`도 응답하지 않는다.

공지 마크다운(`notices/`)을 수정하면 다음 배포의 이미지 빌드에 포함된다. 컨테이너를 재시작만 해서는 이미지 안의 파일이 바뀌지 않는다.

## 롤백 (supervisor)

컨테이너만 내리고 남겨 둔 supervisor 프로그램을 다시 시작한다. 앱 코드는 이 전환에서 동작이 바뀌지 않았고, 기존 `.venv`가 서버에 남아 있으면 그 환경으로 다시 뜬다.

```bash
cd ~/projects/muhanmantle-back
podman compose down
```

`/etc/supervisor/conf.d/muhanmantle.conf`에서 `autostart=true`, `autorestart=true`로 되돌린 뒤:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start muhanmantle
sudo supervisorctl status muhanmantle
python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read())"
```

이미지 빌드에 문제가 있어 코드도 이전 커밋으로 되돌려야 하면 `git checkout` 뒤에 `.venv`에서 `pip install -r requirements.txt`와 필요한 경우 `alembic`을 다시 맞춘다. DB를 다운그레이드하는 절차는 이 문서 범위 밖이다. 이 전환의 마이그레이션은 기존 배포와 같은 `upgrade head`다.

## 로컬에서 DB만 컨테이너로

운영 서버에서는 하지 않는다. 노트북에서만, 운영용 `docker-compose.yml`과 별도 파일이다. `podman-compose` 1.0.6은 Compose profile을 무시해서, 개발용 DB를 같은 파일에 두면 `up`이 서버에서도 MariaDB 컨테이너를 띄운다.

```bash
podman compose -f compose.local-db.yml up -d
```

이때 `DATABASE_URL` 포트는 `3307`이다. `DB_PASSWORD`와 `DB_ROOT_PASSWORD`가 필요하다. API까지 컨테이너로 띄우려면 호스트에 MariaDB가 있거나, URL이 컨테이너에서 도달하는 주소여야 한다. 운영 조합은 호스트 MariaDB + 호스트 네트워크다.

## 이미지 크기

`sentence-transformers`가 PyTorch를 끌어온다. `Containerfile`은 CPU 휠을 설치한다. CUDA 휠은 넣지 않는다. 이미지는 수 GB일 수 있으니 서버 디스크 여유를 확인해 둔다.
