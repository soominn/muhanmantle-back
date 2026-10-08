# API image for the 무한맨틀 backend. Large FastText files are not copied;
# compose mounts ./models on /app/models at runtime.
FROM docker.io/library/python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# gensim and the CPU torch wheel need OpenMP at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# PyPI's default Linux torch wheel is the CUDA build. This server is CPU-only;
# install the CPU wheel first and again after requirements so sentence-transformers
# does not replace it.
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && python -c "import fastapi, gensim, sentence_transformers, torch; assert torch.version.cuda in (None, ''), torch.version.cuda; print('torch', torch.__version__)"

COPY . .
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/models/fasttext /app/models/embedding-cache

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
