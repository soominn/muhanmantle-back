from app.services.stdict_openapi import word_found_in_search_response


def test_word_found_when_item_is_list() -> None:
    payload = {
        "channel": {
            "total": 2,
            "item": [
                {"word": "우주"},
                {"word": "나무"},
            ],
        }
    }
    assert word_found_in_search_response("우주", payload) is True


def test_word_found_when_item_is_single_dict() -> None:
    payload = {
        "channel": {
            "total": 1,
            "item": {"word": "우주"},
        }
    }
    assert word_found_in_search_response("우주", payload) is True


def test_word_not_found() -> None:
    payload = {
        "channel": {
            "total": 1,
            "item": {"word": "우주선"},
        }
    }
    assert word_found_in_search_response("우주", payload) is False


def test_word_found_with_hyphenated_headword() -> None:
    payload = {
        "channel": {
            "total": 1,
            "item": {"word": "소홀-히"},
        }
    }
    assert word_found_in_search_response("소홀히", payload) is True
