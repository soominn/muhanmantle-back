"""
Download word-list source files into muhanmantle-etc/wordlists/.

Usage (from muhanmantle-back/):
    python scripts/download_wordlists.py
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
WORDLISTS = ROOT / "muhanmantle-etc" / "wordlists"

NIKL_BASIC_XLSX_URL = (
    "https://www.korean.go.kr/common/download.do;front=86715401E97FA9B0BE151D80C1225553"
    "?file_path=reportData&c_file_name=1d6d75b9-45cb-49d4-989f-1483c332573a.xlsx"
    "&o_file_name=%EA%B5%AD%EC%96%B4%20%EA%B8%B0%EC%B4%88%20%EC%96%B4%ED%9C%98%20%EC%84%A0%EC%A0%95"
    "%20%EB%B0%8F%20%EC%96%B4%ED%9C%98%20%EB%93%B1%EA%B8%89%ED%99%94%20%EB%AA%A9%EB%A1%9D%20%EC%A0%84%EC%B2%B4.xlsx"
)
NIKL_FREQ_ZIP_URL = (
    "https://www.korean.go.kr/common/download.do;front=A78BD3D47346A8FE532077EAA352B2B9"
    "?file_path=etcData&c_file_name=0907a2ca-3391-47e8-8216-8867c22add5a_0.zip"
    "&o_file_name=%ED%98%84%EB%8C%80%20%EA%B5%AD%EC%96%B4%20%EC%82%AC%EC%9A%A9%20%EB%B9%88%EB%8F%84"
    "%20%EC%A1%B0%EC%82%AC%20%EA%B2%B0%EA%B3%BC%20%ED%8C%8C%EC%9D%BC(%ED%85%8D%EC%8A%A4%ED%8A%B8%20%ED%8C%8C%EC%9D%BC).zip"
)
KO_50K_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/ko/ko_50k.txt"
)
KOFREN_FILES = [
    "adult_frequency_counts_final.csv",
    "all_speakers_frequency_counts_final.csv",
    "children_frequency_counts_final.csv",
    "elderly_frequency_counts_final.csv",
]
KOFREN_BASE = (
    "https://raw.githubusercontent.com/jinseo0904/korean_frequency/main/final_word_frequency"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Zip entry index 3 = 단어 빈도순 (것, 하다, 있다 …)
NIKL_WORD_FREQ_ZIP_INDEX = 3


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip (exists): {dest.relative_to(ROOT)}")
        return
    print(f"download: {dest.relative_to(ROOT)}")
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def _extract_nikl_word_frequency(zip_path: Path, out_path: Path) -> None:
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"skip (exists): {out_path.relative_to(ROOT)}")
        return
    print(f"extract: {out_path.relative_to(ROOT)}")
    with zipfile.ZipFile(zip_path) as zf:
        raw = zf.read(zf.infolist()[NIKL_WORD_FREQ_ZIP_INDEX])
    out_path.write_bytes(raw.decode("cp949", errors="replace").encode("utf-8"))


def main() -> None:
    nikl = WORDLISTS / "nikl"
    kofren = WORDLISTS / "kofren"
    github = WORDLISTS / "github"

    _download(NIKL_BASIC_XLSX_URL, nikl / "basic_vocab_40000.xlsx")
    _download(NIKL_FREQ_ZIP_URL, nikl / "modern_korean_frequency.zip")
    _download(KO_50K_URL, github / "ko_50k.txt")

    for name in KOFREN_FILES:
        _download(f"{KOFREN_BASE}/{name}", kofren / name)

    _extract_nikl_word_frequency(nikl / "modern_korean_frequency.zip", nikl / "word_by_frequency.tsv")
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)
