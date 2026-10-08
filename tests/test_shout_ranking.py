"""Global shout ranking: one count per session per word, across every puzzle."""

import importlib.util
import json
import uuid
from pathlib import Path

from app.models.answer_word import AnswerWord
from app.models.game_session import GameSession
from app.models.game_shout import GameShout

ANSWER = "사과"
OTHER = "바나나"


def _session(client) -> dict:
    client.cookies.clear()
    resp = client.get("/api/game/session")
    assert resp.status_code == 200
    return resp.json()


def _as(client, session_id: str):
    client.cookies.clear()
    return {"X-Game-Session": session_id}


def _guess(client, session_id: str, word: str):
    return client.post(
        "/api/game/session/guess",
        json={"word": word},
        headers=_as(client, session_id),
    )


def _ranking(client):
    client.cookies.clear()
    return client.get("/api/game/shout-ranking")


def test_shout_ranking_works_without_a_session(client):
    resp = _ranking(client)
    assert resp.status_code == 200
    assert resp.json() == {"items": []}
    assert resp.headers.get("set-cookie") is None
    assert resp.cookies.get("mm_session") is None

    again = client.get(
        "/api/game/shout-ranking",
        headers={"X-Game-Session": "not-a-session"},
    )
    assert again.status_code == 200
    assert again.json() == {"items": []}
    assert again.headers.get("set-cookie") is None


def test_same_session_counts_once_across_puzzles_and_repeats(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.add(AnswerWord(answer_word="포도"))
    db.commit()

    s1 = _session(client)["session_id"]
    row = db.get(GameSession, s1)
    row.answer_id = 1
    db.commit()

    assert _guess(client, s1, OTHER).status_code == 200
    assert _guess(client, s1, OTHER).json()["duplicate"] is True

    # Next puzzle for the same session. Guesses reset; the shout must not.
    row.answer_id = 2
    row.guesses = []
    row.gave_up = False
    db.commit()

    again = _guess(client, s1, OTHER)
    assert again.status_code == 200
    assert again.json()["duplicate"] is False
    assert again.json()["answer_id"] == 2

    s2 = _session(client)["session_id"]
    db.get(GameSession, s2).answer_id = 1
    db.commit()
    assert _guess(client, s2, OTHER).status_code == 200
    assert _guess(client, s2, "오렌지").status_code == 200

    ranked = _ranking(client)
    assert ranked.status_code == 200
    assert ranked.headers.get("set-cookie") is None
    payload = ranked.json()
    assert set(payload.keys()) == {"items"}
    assert payload["items"] == [
        {"word": OTHER, "count": 2},
        {"word": "오렌지", "count": 1},
    ]
    for item in payload["items"]:
        assert set(item.keys()) == {"word", "count"}
        assert isinstance(item["count"], int)


def test_ranking_is_global_and_does_not_mark_the_answer(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.add(AnswerWord(answer_word="포도"))
    db.commit()

    s1 = _session(client)["session_id"]
    s2 = _session(client)["session_id"]
    db.get(GameSession, s1).answer_id = 1
    db.get(GameSession, s2).answer_id = 2
    db.commit()

    assert _guess(client, s1, "오렌지").status_code == 200
    assert _guess(client, s2, "포도").status_code == 200
    assert _guess(client, s2, ANSWER).status_code == 200

    client.post("/api/game/session/give-up", headers=_as(client, s1))

    payload = _ranking(client).json()
    assert payload["items"] == [
        {"word": ANSWER, "count": 1},
        {"word": "오렌지", "count": 1},
        {"word": "포도", "count": 1},
    ]
    blob = json.dumps(payload, ensure_ascii=False)
    assert "answer" not in blob
    assert "number" not in blob
    # Give-up reveals 사과 to that session, but the ranking call itself has no reveal.
    assert "revealed_answer" not in payload


def test_invalid_guess_and_give_up_do_not_add_a_shout(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()
    sid = _session(client)["session_id"]

    assert _guess(client, sid, "a").status_code == 400
    assert client.post(
        "/api/game/session/give-up", headers=_as(client, sid)
    ).status_code == 200

    ranked = _ranking(client).json()
    assert ranked == {"items": []}
    assert ANSWER not in json.dumps(ranked, ensure_ascii=False)


def test_shout_ranking_limits_to_top_20_by_count(client, db):
    for n in range(21):
        word = f"순위{n:02d}"
        for i in range(21 - n):
            db.add(
                GameShout(
                    word=word,
                    session_id=f"{n:02d}-{i:02d}-{uuid.uuid4().hex[:8]}",
                )
            )
    db.commit()

    items = _ranking(client).json()["items"]
    assert len(items) == 20
    assert items[0] == {"word": "순위00", "count": 21}
    assert items[-1] == {"word": "순위19", "count": 2}
    assert [item["count"] for item in items] == list(range(21, 1, -1))
    assert all(item["word"] != "순위20" for item in items)


def test_backfill_counts_each_session_word_once():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0005_game_shout.py"
    )
    spec = importlib.util.spec_from_file_location("mig0005", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    words = module._unique_guess_words(
        [
            {"word": "바나나"},
            {"word": "바나나"},
            {"word": " 오렌지 "},
            {"word": ""},
            "nope",
        ]
    )
    assert words == ["바나나", "오렌지"]
    assert module._unique_guess_words('[{"word": "포도"}, {"word": "포도"}]') == ["포도"]
