def merge_setting(request_setting: dict, classification: dict, rag_context: str) -> dict:
    request_setting = dict(request_setting or {})
    classification = classification or {}

    state = request_setting.get("state")
    if not state and "emotionalState" in request_setting:
        state = request_setting.get("emotionalState")
    if state == "skip":
        state = "prefer_not_say"

    tone = request_setting.get("tone")
    if tone == "spicy":
        tone = "rogue_light"

    mode = "night" if classification.get("night_mode_hint") else "default"

    user_mood = None
    if not state or state == "prefer_not_say":
        user_mood = classification.get("mood")

    merged_setting = {
        "mode": mode,
    }

    if state:
        merged_setting["state"] = state
    if tone:
        merged_setting["tone"] = tone
    if user_mood is not None:
        merged_setting["user_mood"] = user_mood

    for key in ("intensity", "risk", "topics"):
        if key in classification and classification.get(key) is not None:
            merged_setting[key] = classification.get(key)

    if rag_context:
        merged_setting["_rag_context"] = rag_context

    return merged_setting
