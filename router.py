"""
מנתב משימות: מחליט אוטומטית בין מודל מקומי לענן.

לוגיקה:
- אותות מורכבות (ארכיטקטורה, אבטחה, למה, debug) → ענן
- אותות פשוטות (כתוב, צור, פרמט, שנה שם) → מקומי
- הודעה ארוכה מ-400 תווים → נקודה נוספת לענן
"""

CLOUD_SIGNALS = [
    # עברית
    "ארכיטקטורה", "תכנון", "אבטחה", "ביצועים", "למה", "הסבר",
    "בעיה", "תקלה", "חקור", "נתח", "השווה",
    # אנגלית
    "architecture", "system design", "security", "performance",
    "why", "explain", "debug", "investigate", "analyze",
    "bottleneck", "vulnerability", "race condition", "tradeoff",
    "should i", "best approach", "best practice",
]

LOCAL_SIGNALS = [
    # עברית
    "כתוב", "צור", "הוסף", "שנה שם", "פרמט", "תעד", "רשום",
    "המר", "תרגם", "בדיקה יחידה", "שלד",
    # אנגלית
    "write", "generate", "create", "add", "rename", "format",
    "document", "boilerplate", "scaffold", "unit test",
    "refactor", "convert", "translate", "stub", "mock",
]


def route(prompt: str) -> str:
    """מחזיר 'local' או 'cloud'."""
    lower = prompt.lower()

    cloud_score = sum(1 for s in CLOUD_SIGNALS if s in lower)
    local_score = sum(1 for s in LOCAL_SIGNALS if s in lower)

    if len(prompt) > 400:
        cloud_score += 2

    # שוויון (כולל 0/0) → מקומי: ברירת מחדל חסכונית
    return "cloud" if cloud_score > local_score else "local"
