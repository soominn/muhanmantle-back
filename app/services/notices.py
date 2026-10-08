"""Read-only notices from markdown files in the repository notices/ folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.core.config import BASE_DIR

NOTICES_DIR = BASE_DIR / "notices"


def list_notices(directory: Path | None = None) -> list[dict[str, str]]:
    """Newest date first. Non-markdown files and notices without title/date are skipped."""
    root = directory if directory is not None else NOTICES_DIR
    if not root.is_dir():
        return []

    parsed: list[tuple[date, dict[str, str]]] = []
    for path in root.iterdir():
        if not path.is_file() or path.suffix != ".md":
            continue
        item = _read_notice(path)
        if item is None:
            continue
        parsed.append(item)

    parsed.sort(key=lambda pair: pair[1]["slug"])
    parsed.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in parsed]


def _read_notice(path: Path) -> tuple[date, dict[str, str]] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    split = _split_frontmatter(text)
    if split is None:
        return None
    front, body = split
    meta = _parse_frontmatter(front)
    if meta is None:
        return None
    notice_date, title = meta
    return notice_date, {
        "slug": path.stem,
        "title": title,
        "date": notice_date.isoformat(),
        "body": body,
    }


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            front = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1 :]).strip("\n")
            return front, body
    return None


def _parse_frontmatter(block: str) -> tuple[date, str] | None:
    """Single-line YAML fields. title and date are required."""
    fields: dict[str, str] = {}
    for raw in block.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        fields[key] = value

    title = fields.get("title", "").strip()
    raw_date = fields.get("date", "").strip()
    if not title or not raw_date:
        return None
    try:
        notice_date = date.fromisoformat(raw_date)
    except ValueError:
        return None
    return notice_date, title
