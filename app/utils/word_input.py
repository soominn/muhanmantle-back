"""Korean word input rules (aligned with the frontend `inputValidation.ts`)."""

from __future__ import annotations

import re

_INVALID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[A-Za-z]+$"),
    re.compile(r"^[ㄱ-ㅎ]+$"),
    re.compile(r"^[ㅏ-ㅣ]+$"),
    re.compile(r"^[0-9]+$"),
    re.compile(r"^[^A-Za-z0-9가-힣ㄱ-ㅎㅏ-ㅣ]+$"),
)


def is_valid_korean_word(word: str) -> bool:
    if not word:
        return False
    return not any(p.match(word) for p in _INVALID_PATTERNS)
