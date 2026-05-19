# ML 모델·캐시 디렉터리

Git에는 **용량이 큰 바이너리를 올리지 않습니다.** 각자 받아 두거나, 배포 서버에서는 S3 등에서 내려받아 이 경로에 두면 됩니다.

## 레이아웃

| 경로 | 용도 |
|------|------|
| `models/fasttext/` | FastText `cc.ko.300.vec` / `cc.ko.300.kv` (및 gensim이 만드는 `.kv.vectors.npy` 등) |
| `models/embedding-cache/` | `SIMILARITY_BACKEND=sentence_transformer` 일 때 BaseWord 임베딩 디스크 캐시 |

## FastText 기본 파일명

- `models/fasttext/cc.ko.300.vec`
- `models/fasttext/cc.ko.300.kv`

다른 위치를 쓰려면 `.env`의 `VEC_FILE`, `KV_FILE`에 절대 경로를 지정하면 됩니다.

## 기존에 레포 루트에 두었던 경우

```bash
cd muhanmantle-back
mkdir -p models/fasttext
mv -n cc.ko.300.vec cc.ko.300.kv models/fasttext/ 2>/dev/null || true
# .npy가 루트에 있으면 같이 이동
mv -n cc.ko.300.kv.vectors.npy models/fasttext/ 2>/dev/null || true
```

## 다운로드 참고

- [FastText Korean vectors](https://fasttext.cc/docs/en/crawl-vectors.html) 등 공식 배포에서 `cc.ko.300.bin` / `.vec` 형태를 받은 뒤, 앱은 `.vec` → `.kv` 변환을 자동으로 할 수 있습니다.
