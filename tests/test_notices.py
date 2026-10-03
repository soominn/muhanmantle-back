"""GET /api/notices reads markdown files and does not touch the game session."""

from pathlib import Path

from sqlalchemy import func, select

from app.models.game_session import GameSession
from app.services.notices import list_notices

SEEDED_BODY = (
    "개인적으로 하려고 만든 게임인데 생각보다 많은 분들이 즐겨 주셔서 업데이트를 조금 했습니다.\n"
    "먼저 포기하면 그 번호의 정답을 알려줍니다. 그리고 Shouts에서 게임에서 사람들이 많이 외친 단어 순위를 볼 수 있습니다.\n"
    "유사도 계산 부분도 나중에 업데이트할 예정입니다. 언제인지는 아직 모릅니다.\n"
    "이제 더 잘 관리해 보겠습니다. 플레이 해주셔서 감사합니다."
)


def test_seed_notice_is_returned_without_a_session(client, db):
    before = db.scalar(select(func.count()).select_from(GameSession)) or 0

    resp = client.get("/api/notices")

    assert resp.status_code == 200
    assert resp.headers.get("set-cookie") is None
    assert resp.cookies.get("mm_session") is None
    after = db.scalar(select(func.count()).select_from(GameSession)) or 0
    assert after == before

    payload = resp.json()
    assert set(payload.keys()) == {"items"}
    notice = next(item for item in payload["items"] if item["slug"] == "2026-10-03-update")
    assert notice == {
        "slug": "2026-10-03-update",
        "title": "업데이트",
        "date": "2026-10-03",
        "body": SEEDED_BODY,
    }
    assert payload["items"][0]["slug"] == "2026-10-03-update"


def test_notices_are_newest_first_and_skip_non_markdown(tmp_path: Path):
    (tmp_path / "2026-01-01-old.md").write_text(
        "---\ntitle: 이전\ndate: 2026-01-01\n---\n\n이전 본문\n",
        encoding="utf-8",
    )
    (tmp_path / "2026-10-04-new.md").write_text(
        "---\ntitle: 최신\ndate: 2026-10-04\n---\n\n최신 본문\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text("not a notice", encoding="utf-8")
    (tmp_path / "broken.md").write_text("no frontmatter\n", encoding="utf-8")

    items = list_notices(tmp_path)

    assert [item["slug"] for item in items] == ["2026-10-04-new", "2026-01-01-old"]
    assert items[0]["title"] == "최신"
    assert items[0]["date"] == "2026-10-04"
    assert items[0]["body"] == "최신 본문"
    assert all(set(item.keys()) == {"slug", "title", "date", "body"} for item in items)
