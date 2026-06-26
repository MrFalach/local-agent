"""
טלמטריה: שורת JSONL אחת לכל קריאה ב-~/.claude/local-agent/telemetry.jsonl.

המטרה — לכייל את הסף ולהוכיח את הערך על תעבורה אמיתית של המשתמש, לא על benchmarks.
stats() קורא את הקובץ ומחזיר סיכום קריא (נתח-ענן, אחוזון-זמן, cold-loads, עלות).
"""

from __future__ import annotations

import json
from pathlib import Path

LOG_PATH = Path.home() / ".claude" / "local-agent" / "telemetry.jsonl"

# מחירון גס למיליון טוקנים (USD) — להערכת עלות בלבד, לא לחיוב.
_PRICE_PER_MTOK = {"input": 3.0, "output": 15.0}


def record(event: dict) -> None:
    """מוסיף שורת JSONL אחת. נכשל בשקט — טלמטריה לעולם לא מפילה קריאה אמיתית."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _est_cost(rows: list[dict]) -> float:
    cost = 0.0
    for r in rows:
        if r.get("provider") == "local":
            continue
        cost += r.get("in_tokens", 0) / 1e6 * _PRICE_PER_MTOK["input"]
        cost += r.get("out_tokens", 0) / 1e6 * _PRICE_PER_MTOK["output"]
    return cost


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def stats() -> str:
    """מחזיר סיכום קריא של הטלמטריה שנצברה עד כה."""
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return "אין עדיין נתוני טלמטריה — הרץ כמה משימות דרך הכלי."

    rows = []
    for ln in lines:
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    if not rows:
        return "אין עדיין נתוני טלמטריה."

    total = len(rows)
    by_provider: dict[str, int] = {}
    for r in rows:
        by_provider[r.get("provider", "?")] = by_provider.get(r.get("provider", "?"), 0) + 1

    latencies = [r["latency_ms"] for r in rows if "latency_ms" in r]
    cold = sum(1 for r in rows if r.get("cold_load"))
    errors = sum(1 for r in rows if not r.get("ok", True))
    pure_cloud = by_provider.get("cloud", 0)
    chain_count = by_provider.get("chain", 0)
    cloud_share = 100 * pure_cloud / total
    chain_share = 100 * chain_count / total

    lines_out = [
        f"local-agent — סיכום {total} קריאות",
        f"  פיצול ספקים : " + ", ".join(f"{k}={v}" for k, v in sorted(by_provider.items())),
        f"  נתח ענן     : {cloud_share:.0f}%  (chain: {chain_share:.0f}%)",
        f"  זמן p50/p95 : {_pct(latencies, 50):.0f}ms / {_pct(latencies, 95):.0f}ms",
        f"  cold-loads  : {cold}",
        f"  שגיאות      : {errors}",
        f"  עלות ענן ~  : ${_est_cost(rows):.2f} (הערכה)",
    ]
    return "\n".join(lines_out)
