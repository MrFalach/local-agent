#!/usr/bin/env python3
"""
אשף התקנה אינטראקטיבי ל-local-agent.

מזהה הכל קודם (אולמה, מודלים מותקנים, מפתח API, ה-CLI), נותן ברירת מחדל לכל שאלה,
ושואל לכל היותר 4 שאלות. בסוף כותב config.json ורושם את ה-MCP אצל קלוד.

    python setup.py

הבחירה היחידה שמכתיבה הכל היא "מה הכי חשוב לך": quality / cost / speed / balanced.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import config

# priority → מודל הענן שייכתב לקונפיג. רק quality מטפס לאופוס; השאר על סונט (רצפת איכות).
CLOUD_MODEL_BY_PRIORITY = {
    "quality":  "claude-opus-4-8",
    "cost":     "claude-sonnet-4-6",
    "speed":    "claude-sonnet-4-6",
    "balanced": "claude-sonnet-4-6",
}
DEFAULT_PULL = "qwen2.5-coder:7b"
SERVER_PATH = Path(__file__).resolve().parent / "server.py"


# ---------- זיהוי (best-effort, לעולם לא זורק) ----------

def _ollama_host() -> str:
    host = os.getenv("OLLAMA_HOST", "127.0.0.1:11434")
    if not host.startswith("http"):
        host = "http://" + host
    return host


def detect_ollama() -> tuple[bool, list[str]]:
    try:
        with urllib.request.urlopen(f"{_ollama_host()}/api/tags", timeout=2) as r:
            data = json.load(r)
        return True, [m["name"] for m in data.get("models", [])]
    except Exception:
        return False, []


def pick_local(models: list[str]) -> str:
    ladder = ["qwen2.5-coder", "deepseek-coder", "codellama", "qwen"]
    for needle in ladder:
        for m in models:
            if needle in m:
                return m
    return models[0] if models else ""


def detect_key() -> bool:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    env = SERVER_PATH.parent / ".env"
    try:
        return "ANTHROPIC_API_KEY=" in env.read_text(encoding="utf-8") and \
            "your_key_here" not in env.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False


# ---------- קלט ----------

def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{prompt}{suffix} > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nבוטל.")
        sys.exit(1)
    return ans or default


def ask_choice(prompt: str, options: list[tuple[str, str]], default_idx: int) -> str:
    print(prompt)
    for i, (_, label) in enumerate(options, 1):
        mark = "  (ברירת מחדל)" if i - 1 == default_idx else ""
        print(f"      {i}) {label}{mark}")
    ans = ask("    בחר מספר", str(default_idx + 1))
    try:
        idx = int(ans) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    except ValueError:
        pass
    return options[default_idx][0]


# ---------- פעולות ----------

def write_config(scope: str, priority: str, local_model: str) -> Path:
    path = config.GLOBAL_CONFIG if scope == "global" else config.PROJECT_CONFIG
    data = {
        "priority": priority,
        "local_model": local_model,            # "" => cloud-only
        "cloud_model": CLOUD_MODEL_BY_PRIORITY[priority],
        "telemetry": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_key(key: str) -> None:
    env = SERVER_PATH.parent / ".env"
    lines = []
    if env.exists():
        lines = [ln for ln in env.read_text(encoding="utf-8").splitlines()
                 if not ln.startswith("ANTHROPIC_API_KEY=")]
    lines.append(f"ANTHROPIC_API_KEY={key}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def register(scope: str) -> None:
    mcp_scope = "user" if scope == "global" else "project"
    cmd = ["claude", "mcp", "add", "--scope", mcp_scope,
           "local-agent", "python3", str(SERVER_PATH)]
    printable = " ".join(cmd)
    if not shutil.which("claude"):
        print(f"\n  ה-CLI של קלוד לא נמצא ב-PATH. הרץ ידנית לאחר ההתקנה:\n    {printable}")
        return
    if ask(f"\n  לרשום עכשיו?\n    {printable}\n  [y/N]", "N").lower() == "y":
        subprocess.run(cmd, check=False)
    else:
        print(f"  דלגתי. להרצה ידנית:\n    {printable}")


def offer_pull() -> str:
    if ask(f"  אין מודלים מותקנים. למשוך {DEFAULT_PULL} (~4.7GB)? [y/N]", "N").lower() == "y":
        subprocess.run(["ollama", "pull", DEFAULT_PULL], check=False)
        return DEFAULT_PULL
    return ""


# ---------- זרימה ראשית ----------

def main() -> None:
    print("local-agent setup\n")
    ollama_up, models = detect_ollama()
    has_key = detect_key()
    has_cli = bool(shutil.which("claude"))

    print(f"[זיהוי] אולמה   : {'רץ' if ollama_up else 'לא רץ'} ({_ollama_host()})")
    print(f"[זיהוי] מודלים  : {', '.join(models) if models else '—'}")
    print(f"[זיהוי] מפתח API: {'נמצא' if has_key else 'לא נמצא'}")
    print(f"[זיהוי] קלוד CLI: {'נמצא' if has_cli else 'לא נמצא'}\n")

    # Q1 — גלובלי / פרויקטלי
    scope = ask_choice(
        "Q1. התקנה [G]לובלית (כל הפרויקטים) או [P]רויקט נוכחי בלבד?",
        [("global", "גלובלי — כל הפרויקטים"), ("project", "פרויקט נוכחי בלבד")], 0)

    # Q2 — מודל מקומי
    if ollama_up and not models:
        local_model = offer_pull()
    elif ollama_up:
        opts = [(m, m) for m in models] + [("", "אין — ענן בלבד")]
        default_idx = next((i for i, (m, _) in enumerate(opts) if m == pick_local(models)), 0)
        local_model = ask_choice("Q2. מודל מקומי (חינם, רץ על המחשב):", opts, default_idx)
    else:
        print("Q2. אולמה לא רץ → מצב ענן בלבד.")
        local_model = ""

    # Q3 — קדימות (הבחירה שמכתיבה הכל)
    priority = ask_choice(
        "Q3. מה הכי חשוב לך? (זה מכתיב את כל השאר)",
        [("quality",  "quality  — התשובות הכי טובות; מטפס לענן בקלות"),
         ("cost",     "cost     — נשאר מקומי; עולה לענן רק כשקשה (מומלץ)"),
         ("speed",    "speed    — התגובות הכי מהירות"),
         ("balanced", "balanced — פיצול חכם")], 1)

    # Q4 — מפתח (רק אם אין)
    if not has_key:
        key = ask("Q4. הדבק מפתח Anthropic API (Enter לדילוג)", "")
        if key:
            write_key(key)
            has_key = True

    # שער: צריך לפחות backend אחד
    if not local_model and not has_key:
        print("\nצריך לפחות backend אחד — או מפתח API או מודל מקומי. לא נכתב כלום.")
        sys.exit(1)

    path = write_config(scope, priority, local_model)
    print(f"\nנכתב {path}")
    if not local_model:
        print("  מצב ענן בלבד. להוספת מודל מקומי בהמשך: התקן אולמה → "
              f"ollama pull {DEFAULT_PULL} → הרץ שוב python setup.py")
    register(scope)
    print("\nסיום. הפעל מחדש את קלוד קוד.")


if __name__ == "__main__":
    main()
