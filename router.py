"""
מנתב משימות: מחליט בין מודל מקומי לענן ומחזיר החלטה מנומקת (לא רק מחרוזת).

לוגיקה:
- סופרים אותות-ענן (ארכיטקטורה, אבטחה, למה, debug...) מול אותות-מקומי (כתוב, צור, פרמט...).
- score = cloud_pts / (cloud_pts + local_pts)  →  "ענניוּת" בטווח 0..1.
- prompt לא מזוהה / עמום (0/0) מקבל score=0.5 — כלומר "לא יודע", ואז הסף מכריע.
- ננתב לענן אם score >= cloud_threshold (מגיע מהקונפיג, נגזר מ-priority).

הערה מהותית: ביטלנו את חוקיית "אורך > 400 תווים → ענן". אורך לא מנבא קושי
ולא צורך-בחשיבה (config ארוך ומכני הולך לענן בטעות; "למה זה נתקע?" קצר נשאר מקומי).
"""

from __future__ import annotations

from dataclasses import dataclass

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

# פעלים מכניים של ייצור-קוד — רמז ש-chain (ענן מתכנן → מקומי מייצר) עשוי להשתלם.
CODEGEN_VERBS = [
    "write", "generate", "create", "scaffold", "refactor", "implement",
    "כתוב", "צור", "שלד", "ממש",
]


@dataclass
class RouteDecision:
    label: str            # "local" | "cloud"
    score: float          # ענניוּת 0..1
    cloud_hits: int
    local_hits: int
    matched: list[str]    # אילו אותות נמצאו (לטלמטריה/דיבוג)
    codegen: bool         # האם נראה כמו ייצור-קוד מכני (רלוונטי ל-chain)


def _matched_signals(lower: str, signals: list[str]) -> list[str]:
    return [s for s in signals if s in lower]


def route(prompt: str, cloud_threshold: float = 0.45) -> RouteDecision:
    """מחזיר RouteDecision לפי הסף שהתקבל מהקונפיג."""
    lower = prompt.lower()

    cloud_matched = _matched_signals(lower, CLOUD_SIGNALS)
    local_matched = _matched_signals(lower, LOCAL_SIGNALS)
    cloud_pts = len(cloud_matched)
    local_pts = len(local_matched)

    total = cloud_pts + local_pts
    score = 0.5 if total == 0 else cloud_pts / total  # 0/0 = "לא יודע" → הסף מכריע

    label = "cloud" if score >= cloud_threshold else "local"
    codegen = any(v in lower for v in CODEGEN_VERBS)

    return RouteDecision(
        label=label,
        score=round(score, 3),
        cloud_hits=cloud_pts,
        local_hits=local_pts,
        matched=cloud_matched + local_matched,
        codegen=codegen,
    )
