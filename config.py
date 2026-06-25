"""
קונפיגורציה רב-שכבתית ל-local-agent.

קדימויות (הגבוה גובר):
  1. משתני סביבה  (LOCAL_AGENT_* / ANTHROPIC_API_KEY)
  2. פרויקטלי     ./.local-agent.json  (תיקיית העבודה הנוכחית)
  3. גלובלי       ~/.claude/local-agent/config.json
  4. ברירות מחדל מובנות

הפרמטר היחיד שהמשתמש בוחר הוא priority (quality|cost|speed|balanced),
והוא זה שגוזר את שאר ברירות המחדל — סף הניתוב, ה-timeout, והאם chain פעיל.
ערך מפורש בקובץ/סביבה תמיד גובר על מה ש-priority גזר.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

GLOBAL_CONFIG = Path.home() / ".claude" / "local-agent" / "config.json"
PROJECT_CONFIG = Path.cwd() / ".local-agent.json"

# priority → ברירות מחדל גזורות.
# cloud_threshold: ננתב לענן אם cloud-score >= threshold.
#   סף נמוך  → קל לעלות לענן (איכות).
#   סף גבוה  → נשארים מקומי (חיסכון).
# prompt ב-0/0 (לא מזוהה/עמום) מקבל score=0.5, ולכן:
#   quality(0.25)→ענן,  cost(0.6)→מקומי,  balanced/speed(0.45)→ענן.
PRIORITY_PROFILES = {
    "quality":  {"cloud_threshold": 0.25, "timeout": 60.0, "chain": True},   # Opus שמור ל-max בעתיד
    "cost":     {"cloud_threshold": 0.60, "timeout": 45.0, "chain": True},
    "speed":    {"cloud_threshold": 0.45, "timeout": 30.0, "chain": False},
    "balanced": {"cloud_threshold": 0.45, "timeout": 45.0, "chain": True},
}

DEFAULTS = {
    "priority":        "cost",
    "local_model":     "qwen2.5-coder:7b",
    "cloud_model":     "claude-sonnet-4-6",   # quality גם על סונט; Opus רק ל-max בעתיד
    "telemetry":       True,
    # שדות אופציונליים שגוברים על מה ש-priority גזר (None = "תגזור מ-priority"):
    "cloud_threshold": None,
    "timeout":         None,
    "chain":           None,
}

# מיפוי שדה → משתנה סביבה. ANTHROPIC_API_KEY מטופל בנפרד ב-providers.
_ENV_KEYS = {
    "priority":        "LOCAL_AGENT_PRIORITY",
    "local_model":     "LOCAL_MODEL",
    "cloud_model":     "CLOUD_MODEL",
    "cloud_threshold": "LOCAL_AGENT_CLOUD_THRESHOLD",
    "timeout":         "LOCAL_AGENT_TIMEOUT",
    "chain":           "LOCAL_AGENT_CHAIN",
}


@dataclass
class Config:
    priority: str
    local_model: str
    cloud_model: str
    telemetry: bool
    cloud_threshold: float
    timeout: float
    chain: bool
    sources: list[str] = field(default_factory=list)  # מאיפה נטענו ערכים (לדיבוג/stats)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _coerce(key: str, value):
    """המרת ערך גולמי (בעיקר ממשתני סביבה, שהם תמיד מחרוזת) לטיפוס הנכון."""
    if value is None:
        return None
    if key in ("cloud_threshold", "timeout"):
        return float(value)
    if key in ("telemetry", "chain"):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    return value


def load() -> Config:
    """טוען קונפיג לפי סדר הקדימויות ומחזיר אובייקט Config מוכן לשימוש."""
    merged = dict(DEFAULTS)
    sources: list[str] = ["defaults"]

    global_cfg = _read_json(GLOBAL_CONFIG)
    if global_cfg:
        merged.update({k: v for k, v in global_cfg.items() if k in DEFAULTS})
        sources.append(str(GLOBAL_CONFIG))

    project_cfg = _read_json(PROJECT_CONFIG)
    if project_cfg:
        merged.update({k: v for k, v in project_cfg.items() if k in DEFAULTS})
        sources.append(str(PROJECT_CONFIG))

    for key, env_name in _ENV_KEYS.items():
        raw = os.getenv(env_name)
        if raw is not None and raw != "":
            merged[key] = _coerce(key, raw)
            sources.append(f"env:{env_name}")

    # priority גוזר את מה שלא הוגדר במפורש
    priority = merged["priority"] if merged["priority"] in PRIORITY_PROFILES else "balanced"
    profile = PRIORITY_PROFILES[priority]
    for key in ("cloud_threshold", "timeout", "chain"):
        if merged.get(key) is None:
            merged[key] = profile[key]

    # מצב cloud-only: אין מודל מקומי → הכל לענן.
    # route מחזיר cloud אם score >= threshold; סף שלילי => תמיד ענן. וגם chain כבוי.
    if not merged.get("local_model"):
        merged["local_model"] = ""
        merged["cloud_threshold"] = -1.0
        merged["chain"] = False

    return Config(
        priority=priority,
        local_model=merged["local_model"],
        cloud_model=merged["cloud_model"],
        telemetry=bool(merged["telemetry"]),
        cloud_threshold=float(merged["cloud_threshold"]),
        timeout=float(merged["timeout"]),
        chain=bool(merged["chain"]),
        sources=sources,
    )
