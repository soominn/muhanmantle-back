"""
Load word candidates from muhanmantle-etc/wordlists/ (and optional Wiktionary fetch).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORDLISTS = ROOT / "muhanmantle-etc" / "wordlists"

BASIC_VOCAB_XLSX = WORDLISTS / "nikl" / "basic_vocab_40000.xlsx"
NIKL_WORD_FREQ_TSV = WORDLISTS / "nikl" / "word_by_frequency.tsv"
KO_50K_TXT = WORDLISTS / "github" / "ko_50k.txt"
KOFREN_CSV = WORDLISTS / "kofren" / "all_speakers_frequency_counts_final.csv"

GRADE_SHEETS = ("1등급(5,000개)", "2등급(2,500개)", "3등급(5,500개)")

# NIKL 빈도 파일 품사: 내용어 위주
NIKL_CONTENT_POS = frozenset({"명", "동", "형", "대", "수"})

# KoFREN(세종 품사): 일반명사·동사·형용사·부사
KOFREN_CONTENT_POS = frozenset({"NNG", "NNP", "VV", "VA", "MAG", "NR"})

# ko_50k 상위 기능어 (자막 코퍼스)
KO_50K_BLOCKLIST = frozenset(
    {
        "내", "그", "난", "내", "네", "우리", "다", "더", "또", "좀", "잘", "왜", "뭐",
        "이", "저", "것", "수", "등", "때", "중", "점", "번", "개", "명", "년", "월", "일",
        "거", "게", "걸", "께", "데", "데요", "예요", "이에요", "있어", "있어요", "없어",
        "합니다", "해요", "했어", "했어요", "한다", "한다고", "하는", "해서", "하지",
        "그래", "그래서", "그런", "그럼", "그리고", "그냥", "그게", "이게", "저게",
        "여기", "거기", "저기", "지금", "오늘", "정말", "진짜", "아니", "아니요", "네",
        "응", "음", "흠", "뭐야", "뭔", "뭔가", "어떻게", "어떤", "언제", "어디", "누가",
        "하지만", "그러나", "그런데", "그래도", "그러면", "때문", "위해", "통해", "대해",
        "하면", "하면서", "하며", "하고", "하다", "이다", "입니다", "습니다",
    }
)

_STRIP_LEXEME_SUFFIX = re.compile(r"\d+$")


def _normalize_surface(word: str) -> str:
    w = (word or "").strip()
    if not w:
        return ""
    return _STRIP_LEXEME_SUFFIX.sub("", w)


def load_basic_vocab_grades_1_to_3() -> list[str]:
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("pip install openpyxl") from exc

    if not BASIC_VOCAB_XLSX.exists():
        raise FileNotFoundError(f"Missing {BASIC_VOCAB_XLSX}. Run scripts/download_wordlists.py")

    words: list[str] = []
    seen: set[str] = set()
    wb = openpyxl.load_workbook(BASIC_VOCAB_XLSX, read_only=True)
    for sheet_name in GRADE_SHEETS:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 2:
                continue
            raw = row[1]
            if raw is None:
                continue
            w = str(raw).strip()
            if not w or w in seen:
                continue
            seen.add(w)
            words.append(w)
    wb.close()
    return words


def load_nikl_word_by_frequency(limit: int | None = None) -> list[str]:
    if not NIKL_WORD_FREQ_TSV.exists():
        raise FileNotFoundError(
            f"Missing {NIKL_WORD_FREQ_TSV}. Run scripts/download_wordlists.py"
        )

    words: list[str] = []
    seen: set[str] = set()
    for line in NIKL_WORD_FREQ_TSV.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        lemma = _normalize_surface(parts[1])
        pos = parts[3].strip() if len(parts) > 3 else ""
        if not lemma or len(lemma) < 2:
            continue
        if pos and pos not in NIKL_CONTENT_POS:
            continue
        if lemma in seen:
            continue
        seen.add(lemma)
        words.append(lemma)
        if limit and len(words) >= limit:
            break
    return words


def load_kofren_by_frequency(limit: int | None = None) -> list[str]:
    if not KOFREN_CSV.exists():
        raise FileNotFoundError(f"Missing {KOFREN_CSV}. Run scripts/download_wordlists.py")

    rows: list[tuple[float, str]] = []
    with KOFREN_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pos = (row.get("POS_TAG") or "").strip()
            if pos not in KOFREN_CONTENT_POS:
                continue
            word = (row.get("WORD") or "").strip()
            if not word or len(word) < 2:
                continue
            try:
                score = float(row.get("COUNT_ADJUST") or row.get("COUNT") or 0)
            except ValueError:
                score = 0.0
            rows.append((score, word))

    rows.sort(key=lambda x: x[0], reverse=True)
    words: list[str] = []
    seen: set[str] = set()
    for _, word in rows:
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
        if limit and len(words) >= limit:
            break
    return words


def load_ko_50k(limit: int | None = None) -> list[str]:
    if not KO_50K_TXT.exists():
        raise FileNotFoundError(f"Missing {KO_50K_TXT}. Run scripts/download_wordlists.py")

    words: list[str] = []
    seen: set[str] = set()
    for line in KO_50K_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 1:
            continue
        word = parts[0].strip()
        if not word or len(word) < 2 or word in KO_50K_BLOCKLIST:
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
        if limit and len(words) >= limit:
            break
    return words


def merge_priority(*lists: list[str]) -> list[str]:
    """Earlier lists win ordering priority; later lists only add new words."""
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for w in lst:
            if w not in seen:
                seen.add(w)
                out.append(w)
    return out


def build_base_word_candidates(*, raw_cap: int = 25_000) -> list[str]:
    """NIKL 단어 빈도순 우선, 부족분은 KoFREN → ko_50k.

    FastText vocab 필터 후에도 ~1만 개가 남도록 raw 후보는 넉넉히 반환합니다.
    """
    merged = merge_priority(
        load_nikl_word_by_frequency(),
        load_kofren_by_frequency(),
        load_ko_50k(),
    )
    return merged[:raw_cap]


def build_answer_word_candidates(wiktionary_words: list[str] | None = None) -> list[str]:
    """국어 기초 어휘 1~3등급 + (선택) 위키 5800."""
    base = load_basic_vocab_grades_1_to_3()
    if wiktionary_words:
        return merge_priority(base, wiktionary_words)
    return base
