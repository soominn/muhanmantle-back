"""Give-up reveal: answer word stays hidden until the player gives up."""

import json

from app.models.answer_word import AnswerWord
from app.models.game_session import GameSession

ANSWER = "사과"
OTHER = "바나나"


def _assert_answer_hidden(payload: dict, answer: str = ANSWER) -> None:
    blob = json.dumps(payload, ensure_ascii=False)
    assert answer not in blob
    assert payload.get("revealed_answer", None) is None


def _session(client) -> dict:
    client.cookies.clear()
    resp = client.get("/api/game/session")
    assert resp.status_code == 200
    return resp.json()


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
