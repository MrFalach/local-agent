#!/usr/bin/env python3
"""
אשף התקנה אינטראקטיבי ל-local-agent.

    python setup.py           — אשף גלובלי מלא (עד 4 שאלות)
    python setup.py --project — 2 שאלות בלבד; יורש מגלובל, שומר .local-agent.json

האשף מזהה חומרה ומציע מודל המתאים ל-RAM הזמין.
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
import hardware

# Catalog of known models: (ollama_tag, required_ram_gb, tags, download_size)
# required_ram_gb — minimum RAM to run comfortably (conservative estimate)
# tags            — primary use-cases shown to the user
MODEL_CATALOG: list[tuple[str, int, list[str], str]] = [
    # Coding-focused
    ("qwen2.5-coder:3b",      4,  ["code"],              "~2.0GB"),
    ("qwen2.5-coder:7b",      8,  ["code"],              "~4.7GB"),
    ("qwen2.5-coder:14b",    16,  ["code"],              "~9.0GB"),
    ("qwen2.5-coder:32b",    32,  ["code"],              "~20GB"),
    ("qwen2.5-coder:72b",    64,  ["code"],              "~45GB"),
    ("deepseek-coder-v2:16b",16,  ["code"],              "~9.1GB"),
    # Math / reasoning
    ("phi4:14b",             16,  ["math", "reasoning"], "~9.1GB"),
    # General + data
    ("qwen2.5:7b",            8,  ["general", "data"],   "~4.7GB"),
    ("qwen2.5:14b",          16,  ["general", "data"],   "~9.0GB"),
    ("qwen2.5:32b",          32,  ["general", "data"],   "~20GB"),
    ("qwen2.5:72b",          64,  ["general", "data"],   "~45GB"),
    # General purpose
    ("gemma3:4b",             6,  ["general"],           "~3.3GB"),
    ("gemma3:12b",           12,  ["general"],           "~8.1GB"),
    ("gemma3:27b",           32,  ["general"],           "~17GB"),
    ("llama3.2:3b",           4,  ["general"],           "~2.0GB"),
    ("llama3.1:8b",           8,  ["general"],           "~4.9GB"),
    ("llama3.3:70b",         64,  ["general"],           "~43GB"),
    ("mistral:7b",            8,  ["general"],           "~4.1GB"),
]

CLOUD_MODEL_BY_PRIORITY = {
    "quality":  "claude-sonnet-4-6",
    "cost":     "claude-sonnet-4-6",
    "speed":    "claude-sonnet-4-6",
    "balanced": "claude-sonnet-4-6",
}
SERVER_PATH = Path(__file__).resolve().parent / "server.py"


# ---------- זיהוי ----------

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


def detect_key() -> bool:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    env = SERVER_PATH.parent / ".env"
    try:
        text = env.read_text(encoding="utf-8")
        return "ANTHROPIC_API_KEY=" in text and "your_key_here" not in text
    except FileNotFoundError:
        return False


def _best_installed(models: list[str]) -> str:
    """מחזיר את המודל הטוב ביותר מהרשימה המותקנת לפי סדר עדיפויות."""
    ladder = ["qwen2.5-coder", "deepseek-coder", "codellama", "qwen"]
    for needle in ladder:
        for m in models:
            if needle in m:
                return m
    return models[0] if models else ""


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

def write_config(path: Path, priority: str, local_model: str) -> None:
    data = {
        "priority":    priority,
        "local_model": local_model,
        "cloud_model": CLOUD_MODEL_BY_PRIORITY[priority],
        "telemetry":   True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def _catalog_entry(tag: str) -> tuple[int, list[str], str] | None:
    """Returns (required_gb, tags, size) for a catalog model, or None."""
    for t, req, tags, size in MODEL_CATALOG:
        if t == tag:
            return req, tags, size
    return None


def _is_installed(tag: str, installed: list[str]) -> bool:
    base = tag.split(":")[0]
    return any(base in m for m in installed)


def _pick_model_q(hw: dict, models: list[str], ollama_up: bool, q_label: str = "Q. Local model") -> str:
    """
    Build a model selection list from:
      1. Hardware-recommended model (top, with ← recommended tag)
      2. Other installed models compatible with this machine
      3. Uninstalled catalog models compatible with this machine
      4. Cloud-only option

    Shows [code] / [general] / [math] tags and [↓ XGB] for uninstalled models.
    Runs `ollama pull` automatically if the user picks an uninstalled model.
    """
    if not ollama_up:
        print(f"{q_label}: Ollama not running → cloud-only mode.")
        return ""

    ram_gb = hw["ram_gb"]
    recommended = hw["model"]
    tier = hw["tier"]

    opts: list[tuple[str, str]] = []
    seen_bases: set[str] = set()

    def _tag_str(tags: list[str]) -> str:
        return "/".join(tags)

    # 1. Hardware-recommended model (always first)
    if recommended:
        base = recommended.split(":")[0]
        seen_bases.add(base)
        entry = _catalog_entry(recommended)
        tags_s = _tag_str(entry[1]) if entry else "code"
        installed = _is_installed(recommended, models)
        status = "[installed]" if installed else f"[↓ {entry[2]}]" if entry else "[not installed]"
        label = f"{recommended}  [{tags_s}]  ← recommended for {ram_gb:.0f}GB RAM  {status}"
        opts.append((recommended, label))

    # 2. Other installed models that fit this machine
    for m in models:
        base = m.split(":")[0]
        if base in seen_bases:
            continue
        entry = _catalog_entry(m)
        if entry and entry[0] > ram_gb:
            continue  # too large for this machine
        seen_bases.add(base)
        tags_s = _tag_str(entry[1]) if entry else "general"
        label = f"{m}  [{tags_s}]  [installed]"
        opts.append((m, label))

    # 3. Uninstalled catalog models that fit this machine
    for tag, req, tags, size in MODEL_CATALOG:
        base = tag.split(":")[0]
        if base in seen_bases:
            continue
        if req > ram_gb:
            continue
        seen_bases.add(base)
        label = f"{tag}  [{_tag_str(tags)}]  [↓ {size}]"
        opts.append((tag, label))

    opts.append(("", "none — cloud only"))

    choice = ask_choice(f"{q_label} (free, runs locally):", opts, 0)

    # Pull if not installed
    if choice and not _is_installed(choice, models):
        entry = _catalog_entry(choice)
        size_hint = f" ({entry[2]})" if entry else ""
        if ask(f"  {choice}{size_hint} is not installed. Pull now? [y/N]", "N").lower() == "y":
            subprocess.run(["ollama", "pull", choice], check=False)

    return choice


# ---------- זרימה ראשית ----------

def main_global() -> None:
    """אשף גלובלי מלא."""
    print("local-agent setup\n")
    hw = hardware.detect()
    ollama_up, models = detect_ollama()
    has_key = detect_key()
    has_cli = bool(shutil.which("claude"))

    chip_str = f" · {hw['chip']}" if hw["chip"] else ""
    print(f"[זיהוי] חומרה   : {hw['ram_gb']:.0f}GB RAM{chip_str} → tier {hw['tier']}")
    print(f"[זיהוי] אולמה   : {'רץ' if ollama_up else 'לא רץ'} ({_ollama_host()})")
    print(f"[זיהוי] מודלים  : {', '.join(models) if models else '—'}")
    print(f"[זיהוי] מפתח API: {'נמצא' if has_key else 'לא נמצא'}")
    print(f"[זיהוי] קלוד CLI: {'נמצא' if has_cli else 'לא נמצא'}\n")

    # Q1 — גלובלי / פרויקטלי
    scope = ask_choice(
        "Q1. התקנה [G]לובלית (כל הפרויקטים) או [P]רויקט נוכחי בלבד?",
        [("global", "גלובלי — כל הפרויקטים"), ("project", "פרויקט נוכחי בלבד")], 0)

    # Q2 — local model (with hardware recommendation and full catalog)
    local_model = _pick_model_q(hw, models, ollama_up, q_label="Q2")

    # Q3 — קדימות
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

    if not local_model and not has_key:
        print("\nצריך לפחות backend אחד — או מפתח API או מודל מקומי. לא נכתב כלום.")
        sys.exit(1)

    path = config.GLOBAL_CONFIG if scope == "global" else config.PROJECT_CONFIG
    write_config(path, priority, local_model)
    print(f"\nנכתב {path}")
    if not local_model:
        print(f"  מצב ענן בלבד. להוספת מודל מקומי: ollama pull {hw['model'] or 'qwen2.5-coder:7b'} → הרץ שוב")
    register(scope)
    print("\nסיום. הפעל מחדש את קלוד קוד.")


def main_project() -> None:
    """מצב --project: 2 שאלות, יורש מגלובל, שומר .local-agent.json."""
    print("local-agent setup --project\n")
    hw = hardware.detect()
    ollama_up, models = detect_ollama()

    # קרא גלובל כברירת מחדל
    from config import _read_json, GLOBAL_CONFIG
    global_cfg = _read_json(GLOBAL_CONFIG)
    default_priority = global_cfg.get("priority", "cost")
    default_model = global_cfg.get("local_model", hw["model"])

    chip_str = f" · {hw['chip']}" if hw["chip"] else ""
    print(f"[חומרה] {hw['ram_gb']:.0f}GB RAM{chip_str} → tier {hw['tier']}")
    print(f"[גלובל] priority={default_priority}, model={default_model or '(ענן בלבד)'}\n")

    # Q1 — קדימות (ברירת מחדל מגלובל)
    priority_opts = [
        ("quality",  "quality  — ענן בקלות"),
        ("cost",     "cost     — מקומי עד כמה שאפשר"),
        ("speed",    "speed    — מהיר תמיד"),
        ("balanced", "balanced — פיצול חכם"),
    ]
    default_p_idx = next((i for i, (k, _) in enumerate(priority_opts) if k == default_priority), 1)
    priority = ask_choice("Q1. קדימות לפרויקט זה:", priority_opts, default_p_idx)

    # Q2 — מודל מקומי (ברירת מחדל מחומרה/גלובל)
    # בנה hw-dict עם הברירת מחדל הנכונה
    hw_for_q = dict(hw)
    hw_for_q["model"] = default_model or hw["model"]
    local_model = _pick_model_q(hw_for_q, models, ollama_up, q_label="Q2")
    # אם לא בחרו שום דבר — קח את ברירת המחדל הגלובלית בלי לשאול שוב
    if local_model == "" and default_model:
        local_model = default_model

    write_config(config.PROJECT_CONFIG, priority, local_model)
    print(f"\nנכתב {config.PROJECT_CONFIG}")
    print("הפעל מחדש את קלוד קוד כדי שהשינויים ייכנסו לתוקף.")


def main() -> None:
    if "--project" in sys.argv:
        main_project()
    else:
        main_global()


if __name__ == "__main__":
    main()
