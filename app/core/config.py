from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Large binaries (FastText, ST disk cache) — see repository `models/README.md`
MODELS_DIR = BASE_DIR / "models"


class Settings(BaseSettings):
    database_url: str

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://muhanmantle.com",
        "https://www.muhanmantle.com",
    ]

    # FastText model files (default: models/fasttext/)
    vec_file: str = str(MODELS_DIR / "fasttext" / "cc.ko.300.vec")
    kv_file: str = str(MODELS_DIR / "fasttext" / "cc.ko.300.kv")

    # ── Similarity backend ────────────────────────────────────────────────────
    # fasttext: gensim KeyedVectors (existing behaviour)
    # sentence_transformer: sentence-transformers embeddings + cosine ranking
    similarity_backend: Literal["fasttext", "sentence_transformer"] = "fasttext"

    sentence_transformer_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    # Optional: "cpu", "cuda", "mps", … — None lets sentence-transformers decide
    sentence_transformer_device: str | None = None

    # Disk cache for ST BaseWord matrix (ChromaDB not required)
    embedding_cache_dir: Path = MODELS_DIR / "embedding-cache"

    # HttpOnly session cookie for /api/game (set SESSION_COOKIE_SECURE=true behind HTTPS)
    session_cookie_name: str = "mm_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    session_cookie_secure: bool = False

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently drop unknown vars (e.g. old Django DEBUG/SECRET_KEY)
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Accept old django-environ mysql:// scheme and transparently convert it
        if v.startswith("mysql://"):
            return v.replace("mysql://", "mysql+pymysql://", 1)
        return v

    @field_validator("similarity_backend", mode="before")
    @classmethod
    def _coerce_similarity_backend(cls, v: object) -> str:
        if v is None or v == "":
            return "fasttext"
        s = str(v).lower().strip()
        if s in (
            "sentence_transformer",
            "sentence-transformer",
            "sbert",
            "st",
            "transformer",
        ):
            return "sentence_transformer"
        return "fasttext"

    @field_validator("embedding_cache_dir", mode="before")
    @classmethod
    def _coerce_embedding_cache_dir(cls, v: object) -> Path:
        if v is None or v == "":
            return MODELS_DIR / "embedding-cache"
        return Path(v)


settings = Settings()
