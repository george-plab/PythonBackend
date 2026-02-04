from services.merge_setting import merge_setting


def test_injects_rag_context_when_present():
    result = merge_setting(request_setting={}, classification={}, rag_context="RAG")
    assert result["_rag_context"] == "RAG"


def test_state_blocks_user_mood_when_defined():
    result = merge_setting(
        request_setting={"state": "triste"},
        classification={"mood": "ansioso"},
        rag_context=None,
    )
    assert "user_mood" not in result


def test_user_mood_set_when_state_missing():
    result = merge_setting(
        request_setting={},
        classification={"mood": "ansioso"},
        rag_context=None,
    )
    assert result["user_mood"] == "ansioso"


def test_user_mood_set_when_state_prefer_not_say():
    result = merge_setting(
        request_setting={"state": "prefer_not_say"},
        classification={"mood": "solo"},
        rag_context=None,
    )
    assert result["user_mood"] == "solo"


def test_tone_spicy_normalizes_to_rogue_light():
    result = merge_setting(
        request_setting={"tone": "spicy"},
        classification={},
        rag_context=None,
    )
    assert result["tone"] == "rogue_light"


def test_night_mode_hint_sets_mode_night():
    result = merge_setting(
        request_setting={},
        classification={"night_mode_hint": True},
        rag_context=None,
    )
    assert result["mode"] == "night"


def test_tone_hint_does_not_override_user_tone():
    result = merge_setting(
        request_setting={"tone": "directo"},
        classification={"tone_hint": "suave"},
        rag_context=None,
    )
    assert result["tone"] == "directo"


def test_legacy_emotional_state_skip_maps_to_prefer_not_say():
    result = merge_setting(
        request_setting={"emotionalState": "skip"},
        classification={"mood": "triste"},
        rag_context=None,
    )
    assert result["state"] == "prefer_not_say"


def test_output_has_no_legacy_keys():
    result = merge_setting(
        request_setting={"emotionalState": "triste", "tone": "suave"},
        classification={"mood": "ansioso"},
        rag_context=None,
    )
    legacy_keys = {"emotionalState", "mood", "night_mode", "rag_context", "tone_hint"}
    assert not legacy_keys.intersection(result.keys())
