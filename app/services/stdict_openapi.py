"""Stdict (표준국어대사전) Open API client helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _normalize_headword(word: str) -> str:
    """Normalize 표제어 for comparison (e.g., '소홀-히' vs '소홀히')."""
    return (
        (word or "")
        .strip()
        .replace("-", "")
        .replace("‐", "")
        .replace("‑", "")
        .replace("‒", "")
        .replace("–", "")
        .replace("—", "")
        .replace("―", "")
        .replace(" ", "")
    )


def fetch_search_json(
    query: str,
    *,
    key: str,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "key": key,
            "q": (query or "").strip(),
            "req_type": "json",
            "advanced": "y",
            "target": 1,  # 표제어
            "method": "exact",
            "start": 1,
            "num": 10,
        }
    )
    url = f"https://stdict.korean.go.kr/api/search.do?{params}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"Stdict HTTP {e.code}: {detail or e.reason}") from e
    return json.loads(body)


def word_found_in_search_response(word: str, payload: dict[str, Any]) -> bool:
    """True when `word` appears exactly in channel.item[*].word."""
    q = _normalize_headword(word)
    if not q:
        return False

    channel = payload.get("channel")
    if not isinstance(channel, dict):
        return False

    total = int(channel.get("total") or 0)
    if total <= 0:
        return False

    items = channel.get("item")
    if items is None:
        return False
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            continue
        w = _normalize_headword(str(item.get("word", "")))
        if w == q:
            return True
    return False
