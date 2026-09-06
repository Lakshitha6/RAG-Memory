def build_preference_snippet(prefs: dict | None) -> str:

    """ Helper function to structure the preference context """

    if not prefs:
        return "No preferences set - use English, concise answers."

    topics = ", ".join(prefs.get("common_queries") or []) or "none recorded"
    summary = prefs.get("summary") or ""
    return (
        f"Language: {prefs.get('preferred_language', 'en')}. "
        f"Detail level: {prefs.get('response_detail_level', 'concise')}. "
        f"Common topics: {topics}. "
        f"{'Previous context: ' + summary if summary else ''}"
    ).strip()