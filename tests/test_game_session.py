"""Tests for /api/game session + guess + reset."""

import uuid

import pytest

from app.models.answer_word import AnswerWord


def test_get_session_empty_db(client):
    resp = client.get("/api/game/session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 0
    assert data["answer_id"] is None
    assert data["guesses"] == []
    assert data["is_correct"] is False
    uuid.UUID(data["session_id"])
    assert resp.cookies.get("mm_session")


def test_get_session_with_answers(client, db):
    db.add(AnswerWord(answer_word="사과"))
    db.commit()

    resp = client.get("/api/game/session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["answer_id"] == 1
    assert resp.cookies.get("mm_session")

    resp2 = client.get("/api/game/session")
    assert resp2.json()["answer_id"] == 1


def test_session_reuse_via_x_game_session_header(client, db):
    db.add(AnswerWord(answer_word="사과"))
    db.commit()

    r1 = client.get("/api/game/session")
    sid = r1.json()["session_id"]
    aid = r1.json()["answer_id"]
    client.cookies.clear()
    r2 = client.get("/api/game/session", headers={"X-Game-Session": sid})
    assert r2.json()["answer_id"] == aid
    assert r2.json()["session_id"] == sid


def test_guess_and_duplicate(client, db):
    db.add(AnswerWord(answer_word="사과"))
    db.commit()

    client.get("/api/game/session")
    r1 = client.post("/api/game/session/guess", json={"word": "바나나"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["duplicate"] is False
    assert len(d1["guesses"]) == 1
    assert d1["guesses"][0]["word"] == "바나나"

    r2 = client.post("/api/game/session/guess", json={"word": "바나나"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["duplicate"] is True
    assert len(d2["guesses"]) == 1


def test_guess_invalid_word(client, db):
    db.add(AnswerWord(answer_word="사과"))
    db.commit()
    client.get("/api/game/session")

    r = client.post("/api/game/session/guess", json={"word": "a"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_reset_changes_answer(client, db):
    db.add(AnswerWord(answer_word="사과"))
    db.add(AnswerWord(answer_word="바나나"))
    db.commit()

    client.get("/api/game/session")
    r0 = client.post("/api/game/session/guess", json={"word": "바나나"})
    assert r0.status_code == 200
    before_aid = r0.json()["answer_id"]

    r = client.post("/api/game/session/reset")
    assert r.status_code == 200
    d = r.json()
    assert d["answer_id"] in (1, 2)
    assert d["answer_id"] != before_aid
    assert d["guesses"] == []
    assert d["is_correct"] is False


def test_word_input_validation():
    from app.utils.word_input import is_valid_korean_word

    assert is_valid_korean_word("사과") is True
    assert is_valid_korean_word("물") is True
    assert is_valid_korean_word("a") is False
    assert is_valid_korean_word("ㄱ") is False
    assert is_valid_korean_word("") is False
