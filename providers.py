"""ספקי מודל: מקומי (אולמה) וענן (אנתרופיק)."""

import os
import ollama
import anthropic
from dotenv import load_dotenv

load_dotenv()

LOCAL_MODEL_CODE = os.getenv("LOCAL_MODEL", "qwen2.5-coder:7b")
LOCAL_MODEL_GENERAL = os.getenv("LOCAL_MODEL_GENERAL", "gemma4:12b")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "claude-sonnet-4-6")

_anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

CODE_SYSTEM_PROMPT = "You are a code generation assistant. Output code only — no explanations, no markdown prose, no instructions. Just the raw code block."

CODE_KEYWORDS = {"write", "generate", "create", "refactor", "כתוב", "צור", "שלד", "scaffold", "stub", "test"}

def ask_local(prompt: str) -> str:
    is_code_task = any(k in prompt.lower() for k in CODE_KEYWORDS)
    if is_code_task:
        model = LOCAL_MODEL_CODE
        messages = [
            {"role": "system", "content": CODE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    else:
        model = LOCAL_MODEL_GENERAL
        messages = [{"role": "user", "content": prompt}]

    response = ollama.chat(model=model, messages=messages)
    return response.message.content


def ask_cloud(prompt: str) -> str:
    message = _anthropic.messages.create(
        model=CLOUD_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
