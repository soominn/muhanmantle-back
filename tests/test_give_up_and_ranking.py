"""Give-up reveal and per-answer shout ranking."""

import importlib.util
import json
import uuid
from pathlib import Path

from app.models.answer_word import AnswerWord
from app.models.game_session import GameSession
from app.models.game_shout import GameShout

ANSWER = "사과"
OTHER = "바나나"


def _assert_answer_hidden(payload: dict, answer: str = ANSWER) -> None:
    blob = json.dumps(payload, ensure_ascii=False)
    assert answer not in blob
    revealed = payload.get("revealed_answer", None)
    assert revealed is None


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


_PUBLIC_KEYS = {
    "session_id",
    "answer_id",
    "total_count",
    "guesses",
    "is_correct",
    "correct_attempt_count",
}


def test_guess_and_session_hide_answer_before_give_up(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()

    session = _session(client)
    _assert_answer_hidden(session)
    assert session["revealed_answer"] is None
    assert session["answer_id"] == 1

    guessed = client.post("/api/game/session/guess", json={"word": OTHER})
    assert guessed.status_code == 200
    body = guessed.json()
    assert body["duplicate"] is False
    assert set(body.keys()) == {*_PUBLIC_KEYS, "duplicate"}
    _assert_answer_hidden(body)
    assert body["guesses"][0]["word"] == OTHER


def test_give_up_reveals_screen_number_and_persists(client, db):
    db.add(AnswerWord(answer_word="포도"))
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()

    session = _session(client)
    sid = session["session_id"]
    # Screen copy is "{answer_id}번째 정답", not the length of answer_history.
    row = db.get(GameSession, sid)
    row.answer_id = 2
    row.answer_history = [1]
    db.commit()

    client.post("/api/game/session/guess", json={"word": OTHER})

    given = client.post("/api/game/session/give-up")
    assert given.status_code == 200
    data = given.json()
    assert set(data.keys()) == {*_PUBLIC_KEYS, "revealed_answer"}
    assert data["session_id"] == sid
    assert data["answer_id"] == 2
    assert data["is_correct"] is False
    assert data["guesses"][0]["word"] == OTHER
    assert data["revealed_answer"] == {"number": 2, "word": ANSWER}
    assert isinstance(data["revealed_answer"]["number"], int)
    assert isinstance(data["revealed_answer"]["word"], str)
    # number is the on-screen N, which the client already reads from answer_id.
    assert data["revealed_answer"]["number"] == data["answer_id"]
    assert data["revealed_answer"]["number"] != len(row.answer_history)

    again = client.post("/api/game/session/give-up")
    assert again.status_code == 200
    assert again.json()["revealed_answer"] == data["revealed_answer"]
    assert again.json()["guesses"] == data["guesses"]

    refreshed = client.get("/api/game/session")
    assert refreshed.json()["revealed_answer"] == {"number": 2, "word": ANSWER}
    assert refreshed.json()["answer_id"] == 2
    assert refreshed.json()["guesses"][0]["word"] == OTHER


def test_guess_after_give_up_still_omits_answer_word(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()
    _session(client)
    assert client.post("/api/game/session/give-up").status_code == 200

    guessed = client.post("/api/game/session/guess", json={"word": OTHER})
    assert guessed.status_code == 200
    body = guessed.json()
    assert "revealed_answer" not in body
    _assert_answer_hidden(body)

    refreshed = client.get("/api/game/session")
    assert refreshed.json()["revealed_answer"] == {"number": 1, "word": ANSWER}


def test_reset_clears_give_up_reveal(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.add(AnswerWord(answer_word="포도"))
    db.commit()
    _session(client)
    client.post("/api/game/session/give-up")

    reset = client.post("/api/game/session/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["revealed_answer"] is None
    assert body["guesses"] == []
    assert body["is_correct"] is False
    _assert_answer_hidden(body, ANSWER)
    _assert_answer_hidden(body, "포도")

    refreshed = client.get("/api/game/session")
    assert refreshed.json()["revealed_answer"] is None
    _assert_answer_hidden(refreshed.json(), ANSWER)
    _assert_answer_hidden(refreshed.json(), "포도")


def test_give_up_without_answer(client):
    _session(client)
    resp = client.post("/api/game/session/give-up")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_shout_ranking_counts_distinct_sessions_for_current_answer(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()

    s1 = _session(client)["session_id"]
    s2 = _session(client)["session_id"]
    s3 = _session(client)["session_id"]
    assert len({s1, s2, s3}) == 3

    assert _guess(client, s1, OTHER).status_code == 200
    assert _guess(client, s1, OTHER).json()["duplicate"] is True
    assert _guess(client, s1, "오렌지").status_code == 200
    assert _guess(client, s2, OTHER).status_code == 200
    assert _guess(client, s3, OTHER).status_code == 200
    assert _guess(client, s3, "포도").status_code == 200
    # The answer word counts when somebody actually submits it, with no answer flag.
    assert _guess(client, s2, ANSWER).status_code == 200

    ranked = client.get("/api/game/session/shout-ranking", headers=_as(client, s1))
    assert ranked.status_code == 200
    payload = ranked.json()
    assert set(payload.keys()) == {"items"}
    assert payload["items"] == [
        {"word": OTHER, "count": 3},
        {"word": ANSWER, "count": 1},
        {"word": "오렌지", "count": 1},
        {"word": "포도", "count": 1},
    ]
    for item in payload["items"]:
        assert set(item.keys()) == {"word", "count"}

    # Give-up alone does not insert the answer, and a repeat shout does not add a count.
    fresh = _session(client)["session_id"]
    client.post("/api/game/session/give-up", headers=_as(client, fresh))
    after = client.get(
        "/api/game/session/shout-ranking", headers=_as(client, fresh)
    )
    assert after.json()["items"] == payload["items"]


def test_shout_ranking_is_scoped_to_the_current_answer(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.add(AnswerWord(answer_word="포도"))
    db.commit()

    s1 = _session(client)["session_id"]
    s2 = _session(client)["session_id"]
    db.get(GameSession, s1).answer_id = 1
    db.get(GameSession, s2).answer_id = 2
    db.commit()

    assert _guess(client, s1, OTHER).status_code == 200
    assert _guess(client, s2, OTHER).status_code == 200
    assert _guess(client, s2, "오렌지").status_code == 200

    one = client.get("/api/game/session/shout-ranking", headers=_as(client, s1))
    two = client.get("/api/game/session/shout-ranking", headers=_as(client, s2))
    assert one.json()["items"] == [{"word": OTHER, "count": 1}]
    assert two.json()["items"] == [
        {"word": OTHER, "count": 1},
        {"word": "오렌지", "count": 1},
    ]


def test_shout_survives_reset_and_same_session_is_not_counted_twice(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()
    sid = _session(client)["session_id"]
    assert _guess(client, sid, OTHER).status_code == 200

    reset = client.post("/api/game/session/reset", headers=_as(client, sid))
    assert reset.status_code == 200
    assert reset.json()["guesses"] == []
    assert reset.json()["answer_id"] == 1

    ranked = client.get("/api/game/session/shout-ranking", headers=_as(client, sid))
    assert ranked.json()["items"] == [{"word": OTHER, "count": 1}]

    again = _guess(client, sid, OTHER)
    assert again.status_code == 200
    assert again.json()["duplicate"] is False
    ranked = client.get("/api/game/session/shout-ranking", headers=_as(client, sid))
    assert ranked.json()["items"] == [{"word": OTHER, "count": 1}]


def test_shout_ranking_limits_to_top_20(client, db):
    db.add(AnswerWord(answer_word=ANSWER))
    db.commit()
    sid = _session(client)["session_id"]

    for n in range(21):
        word = f"순위{n:02d}"
        for i in range(21 - n):
            db.add(
                GameShout(
                    answer_id=1,
                    word=word,
                    session_id=f"{n:02d}-{i:02d}-{uuid.uuid4().hex[:8]}",
                )
            )
    db.commit()

    ranked = client.get("/api/game/session/shout-ranking", headers=_as(client, sid))
    items = ranked.json()["items"]
    assert len(items) == 20
    assert items[0] == {"word": "순위00", "count": 21}
    assert items[-1] == {"word": "순위19", "count": 2}
    assert [item["count"] for item in items] == list(range(21, 1, -1))
    assert all(item["word"] != "순위20" for item in items)


def test_shout_ranking_empty_without_answer(client):
    _session(client)
    ranked = client.get("/api/game/session/shout-ranking")
    assert ranked.status_code == 200
    assert ranked.json() == {"items": []}


def test_backfill_counts_each_session_word_once():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0004_game_give_up_and_shout.py"
    )
    spec = importlib.util.spec_from_file_location("mig0004", path)
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
