"""
שרת MCP — ניתוב מנומק בין מודל מקומי לענן, מכויל לפי priority של המשתמש.

כלים חשופים לקלוד קוד:
  dev(task)     — משימת פיתוח, מנותבת אוטומטית (כולל מסלול chain)
  ask(question) — שאלה טכנית, מנותבת אוטומטית
  local(prompt) — כפה מקומי
  cloud(prompt) — כפה ענן
  stats()       — סיכום טלמטריה (נתח-ענן, זמנים, עלות מוערכת)
"""

import asyncio
import time

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import config
import providers
import telemetry
from router import route

app = Server("local-agent")

CFG = config.load()

# מיפוי: שם כלי → (מפתח ארגומנט, ספק מאולץ או None לניתוב אוטומטי)
TOOL_MAP = {
    "dev":   ("task",     None),
    "ask":   ("question", None),
    "local": ("prompt",   "local"),
    "cloud": ("prompt",   "cloud"),
}


def _run(prompt: str, tool: str, forced: str | None) -> str:
    """מבצע קריאה אחת, רושם טלמטריה בנקודת-החנק, ומחזיר טקסט עם כותרת קצרה."""
    decision = None
    if forced:
        provider = forced
    else:
        decision = route(prompt, CFG.cloud_threshold)
        # chain רק כשמשתלם: priority מאשר, יש מודל מקומי, נראה ייצור-קוד מכני, והוחלט ענן.
        if CFG.chain and CFG.local_model and decision.label == "cloud" and decision.codegen:
            provider = "chain"
        else:
            provider = decision.label

    start = time.perf_counter()
    ok, error = True, None
    try:
        if provider == "chain":
            result = providers.chain(prompt, CFG)
        elif provider == "cloud":
            result = providers.ask_cloud(prompt, CFG)
        else:
            result = providers.ask_local(prompt, CFG)
    except RuntimeError as e:
        ok, error = False, str(e)
        latency_ms = (time.perf_counter() - start) * 1000
        _log(tool, provider, decision, prompt, latency_ms, None, ok, error)
        raise

    latency_ms = (time.perf_counter() - start) * 1000
    _log(tool, provider, decision, prompt, latency_ms, result, ok, error)

    tag = f"[{result.provider.upper()} {result.model} · {latency_ms / 1000:.1f}s"
    if decision is not None:
        tag += f" · score {decision.score}"
    tag += "]"
    return f"{tag}\n\n{result.text}"


def _log(tool, provider, decision, prompt, latency_ms, result, ok, error):
    if not CFG.telemetry:
        return
    event = {
        "tool": tool,
        "provider": provider,
        "route_score": decision.score if decision else None,
        "cloud_hits": decision.cloud_hits if decision else None,
        "local_hits": decision.local_hits if decision else None,
        "model": result.model if result else None,
        "prompt_len": len(prompt),
        "latency_ms": round(latency_ms),
        "cold_load": latency_ms > 15000,
        "in_tokens": result.in_tokens if result else 0,
        "out_tokens": result.out_tokens if result else 0,
        "cached_tokens": result.cached_tokens if result else 0,
        "out_chars": len(result.text) if result else 0,
        "ok": ok,
        "error": error,
    }
    telemetry.record(event)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dev",
            description="משימת פיתוח — מנותבת אוטומטית למקומי/ענן/chain לפי מורכבות וקדימות",
            inputSchema={"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
        ),
        Tool(
            name="ask",
            description="שאלה טכנית — מנותבת אוטומטית",
            inputSchema={"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
        ),
        Tool(
            name="local",
            description="שלח ישירות למודל המקומי (בלי ניתוב)",
            inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]},
        ),
        Tool(
            name="cloud",
            description="שלח ישירות לקלוד בענן (בלי ניתוב)",
            inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]},
        ),
        Tool(
            name="stats",
            description="סיכום טלמטריה — נתח-ענן, זמני תגובה, cold-loads, עלות מוערכת",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "stats":
        return [TextContent(type="text", text=telemetry.stats())]

    if name not in TOOL_MAP:
        return [TextContent(type="text", text=f"כלי לא מוכר: {name}")]

    arg_key, forced = TOOL_MAP[name]
    prompt = arguments[arg_key]

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run, prompt, name, forced),
            timeout=CFG.timeout,
        )
    except asyncio.TimeoutError:
        # timeout מקומי קצר משמעו שכנראה קרה swap — הסבר ובקש כפיית ענן.
        result = (f"[TIMEOUT] חריגה מ-{CFG.timeout:.0f} שניות. "
                  f"ייתכן שהמודל המקומי נטען מהדיסק — נסה שוב, או השתמש ב-cloud() למשימה זו.")
    except RuntimeError as e:
        result = f"[ERROR] {e}"

    return [TextContent(type="text", text=result)]


async def main():
    providers.warm_up(CFG)  # מחמם את המודל המקומי כדי שהקריאה הראשונה לא תהיה cold-load
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
