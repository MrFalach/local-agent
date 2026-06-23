"""ספקי מודל: מקומי (אולמה) וענן (אנתרופיק)."""

import os
import ollama
import anthropic
from dotenv import load_dotenv

load_dotenv()

LOCAL_MODEL_CODE = os.getenv("LOCAL_MODEL", "qwen2.5-coder:7b")
LOCAL_MODEL_GENERAL = os.getenv("LOCAL_MODEL_GENERAL", "gemma4:12b")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "claude-sonnet-4-6")

CODE_SYSTEM_PROMPT = (
    "You are a code generation assistant. "
    "Output code only — no explanations, no markdown prose, no instructions. "
    "Just the raw code block."
)

CODE_KEYWORDS = {
    "write", "generate", "create", "refactor",
    "כתוב", "צור", "שלד", "scaffold", "stub", "test",
}

# lazy-init: נוצר רק בפעם הראשונה שקוראים לענן
_anthropic_client: anthropic.Anthropic | None = None


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY חסר — הוסף אותו ל-.env")
        _anthropic_client = anthropic.Anthropic(api_key=key)
    return _anthropic_client


def ask_local(prompt: str) -> str:
    is_code_task = any(k in prompt.lower() for k in CODE_KEYWORDS)
    model = LOCAL_MODEL_CODE if is_code_task else LOCAL_MODEL_GENERAL
    messages = (
        [{"role": "system", "content": CODE_SYSTEM_PROMPT},
         {"role": "user", "content": prompt}]
        if is_code_task
        else [{"role": "user", "content": prompt}]
    )
    try:
        response = ollama.chat(model=model, messages=messages)
        return response.message.content
    except Exception as e:
        raise RuntimeError(f"שגיאת מודל מקומי ({model}): {e}") from e


def ask_cloud(prompt: str) -> str:
    try:
        message = _get_anthropic().messages.create(
            model=CLOUD_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
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
    return message.content[0].text
