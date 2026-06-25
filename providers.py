"""ספקי מודל: מקומי (אולמה) וענן (אנתרופיק).

עיצוב:
- מודל מקומי יחיד תושב (resident) — אין החלפת מודלים חמה שעולה 20-40 שניות.
  keep_alive=-1 שומר אותו טעון; warm_up() מחמם אותו בעליית השרת.
- ask_cloud משתמש ב-prompt caching על ה-system prefix (חיסכון בעלות בקריאות חוזרות).
- כל ספק מחזיר ProviderResult עם ספירת טוקנים — בשביל טלמטריה אמיתית.
- chain(): ענן מתכנן בקצרה (max_tokens קטן, יקר) → מקומי מייצר את הגוף (חינם).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic
import ollama
from dotenv import load_dotenv

import config

load_dotenv()

CODE_SYSTEM_PROMPT = (
    "You are a code generation assistant. "
    "Output code only — no explanations, no markdown prose, no instructions. "
    "Just the raw code block."
)

CODE_KEYWORDS = {
    "write", "generate", "create", "refactor",
    "כתוב", "צור", "שלד", "scaffold", "stub", "test",
}

# keep_alive=-1 → אולמה שומר את המודל טעון ללא הגבלת זמן (מודל תושב יחיד).
_KEEP_ALIVE = -1

_anthropic_client: anthropic.Anthropic | None = None


@dataclass
class ProviderResult:
    text: str
    provider: str          # "local" | "cloud"
    model: str
    in_tokens: int = 0
    out_tokens: int = 0
    cached_tokens: int = 0


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY חסר — הוסף אותו ל-.env או הרץ python setup.py")
        _anthropic_client = anthropic.Anthropic(api_key=key)
    return _anthropic_client


def _is_code_task(prompt: str) -> bool:
    return any(k in prompt.lower() for k in CODE_KEYWORDS)


def ask_local(prompt: str, cfg: config.Config) -> ProviderResult:
    model = cfg.local_model
    if not model:
        raise RuntimeError("אין מודל מקומי מוגדר (מצב cloud-only) — הרץ python setup.py כדי להוסיף אחד")
    if _is_code_task(prompt):
        messages = [
            {"role": "system", "content": CODE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    try:
        resp = ollama.chat(model=model, messages=messages, keep_alive=_KEEP_ALIVE)
    except Exception as e:
        raise RuntimeError(f"שגיאת מודל מקומי ({model}): {e}") from e

    return ProviderResult(
        text=resp.message.content,
        provider="local",
        model=model,
        in_tokens=getattr(resp, "prompt_eval_count", 0) or 0,
        out_tokens=getattr(resp, "eval_count", 0) or 0,
    )


def ask_cloud(prompt: str, cfg: config.Config, max_tokens: int = 4096,
              system: str | None = None) -> ProviderResult:
    model = cfg.cloud_model
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        # prompt caching: ה-prefix היציב נשמר במטמון ומוזל בקריאות חוזרות.
        kwargs["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]

    try:
        message = _get_anthropic().messages.create(**kwargs)
    except RuntimeError:
        raise
    except anthropic.AuthenticationError:
        raise RuntimeError("ANTHROPIC_API_KEY לא תקין") from None
    except anthropic.RateLimitError as e:
        raise RuntimeError(f"מגבלת קצב ענן: {e}") from e
    except Exception as e:
        raise RuntimeError(f"שגיאת מודל ענן: {e}") from e

    if not message.content or not hasattr(message.content[0], "text"):
        raise RuntimeError("תגובה לא צפויה ממודל הענן")

    usage = message.usage
    return ProviderResult(
        text=message.content[0].text,
        provider="cloud",
        model=model,
        in_tokens=getattr(usage, "input_tokens", 0) or 0,
        out_tokens=getattr(usage, "output_tokens", 0) or 0,
        cached_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
    )


# spec קצר מהענן מנחה את הייצור המקומי — הוראות בלבד, לא קוד מלא.
_PLAN_SYSTEM = (
    "You are a senior engineer writing a TERSE implementation spec for another model to code from. "
    "Output a short numbered plan: signatures, key steps, edge cases. No prose, no full code."
)


def chain(prompt: str, cfg: config.Config) -> ProviderResult:
    """ענן מתכנן בקצרה (יקר אך קטן) → מקומי מייצר את הגוף (חינם).

    הכלכלה עובדת רק בכיוון הזה: פלט-ענן קטן ויקר, גוף-קוד גדול וחינמי.
    """
    plan = ask_cloud(prompt, cfg, max_tokens=600, system=_PLAN_SYSTEM)

    gen_prompt = (
        f"Implement the following task.\n\nTASK:\n{prompt}\n\n"
        f"APPROVED PLAN (follow it):\n{plan.text}"
    )
    body = ask_local(gen_prompt, cfg)

    # Only cloud (planning) tokens are counted for cost — local generation is free.
    return ProviderResult(
        text=body.text,
        provider="chain",
        model=f"{cfg.cloud_model}+{cfg.local_model}",
        in_tokens=plan.in_tokens,
        out_tokens=plan.out_tokens,
        cached_tokens=plan.cached_tokens,
    )


def warm_up(cfg: config.Config) -> None:
    """מחמם את המודל המקומי בעליית השרת כדי שהקריאה הראשונה לא תהיה cold-load."""
    if not cfg.local_model:
        return
    try:
        ollama.chat(
            model=cfg.local_model,
            messages=[{"role": "user", "content": "ok"}],
            keep_alive=_KEEP_ALIVE,
            options={"num_predict": 1},
        )
    except Exception:
        pass  # אם אולמה לא רץ — נתגלה בקריאה אמיתית עם הודעת שגיאה ברורה
