"""
זיהוי חומרה — RAM → tier → המלצת מודל מקומי.

tier לפי RAM זמין:
  < 8 GB   → cloud-only (אין מספיק זיכרון)
  8–16 GB  → qwen2.5-coder:7b
  16–32 GB → qwen2.5-coder:14b
  32–64 GB → qwen2.5-coder:32b
  64 GB+   → qwen2.5-coder:72b
"""

from __future__ import annotations

import platform
import subprocess


def _ram_bytes() -> int:
    """RAM בבייטים, best-effort. מחזיר 0 אם לא ניתן לזהות."""
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip())
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


def _chip_name() -> str:
    """שם ה-chip לתצוגה, best-effort."""
    try:
        if platform.system() == "Darwin":
            name = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            if not name:
                # Apple Silicon: brand_string ריק; נחזיר את model identifier
                name = subprocess.check_output(
                    ["sysctl", "-n", "hw.model"], text=True
                ).strip()
            return name
        if platform.system() == "Linux":
            out = subprocess.check_output(
                ["grep", "-m1", "model name", "/proc/cpuinfo"], text=True
            )
            return out.split(":", 1)[-1].strip()
    except Exception:
        pass
    return ""


# threshold (GB, exclusive upper bound) → (tier label, ollama model tag)
_TIERS = [
    (16,           "7b",  "qwen2.5-coder:7b"),
    (32,           "14b", "qwen2.5-coder:14b"),
    (64,           "32b", "qwen2.5-coder:32b"),
    (float("inf"), "72b", "qwen2.5-coder:72b"),
]


def detect() -> dict:
    """
    מזהה חומרה ומחזיר dict:
      ram_gb  — RAM בGB (מעוגל לעשרית)
      tier    — "7b" | "14b" | "32b" | "cloud-only"
      model   — תג המודל המומלץ (ריק אם cloud-only)
      chip    — שם ה-chip לתצוגה
    """
    ram = _ram_bytes()
    ram_gb = ram / (1024 ** 3) if ram else 0.0
    chip = _chip_name()

    if ram_gb < 8:
        return {"ram_gb": round(ram_gb, 1), "tier": "cloud-only", "model": "", "chip": chip}

    for threshold, tier, model in _TIERS:
        if ram_gb < threshold:
            return {"ram_gb": round(ram_gb, 1), "tier": tier, "model": model, "chip": chip}

    # לא אמור להגיע לכאן (inf תמיד תופס), אבל כ-fallback:
    return {"ram_gb": round(ram_gb, 1), "tier": "72b", "model": "qwen2.5-coder:72b", "chip": chip}
