"""
שרת MCP — ניתוב אוטומטי בין מודל מקומי לענן.

כלים חשופים לקלוד קוד:
  dev(task)     — משימת פיתוח, מנותבת אוטומטית
  ask(question) — שאלה טכנית, מנותבת אוטומטית
  local(prompt) — כפה מקומי
  cloud(prompt) — כפה ענן
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from router import route
from providers import ask_local, ask_cloud

app = Server("local-agent")

MODEL_TIMEOUT = 180.0  # שניות — גמה 4 12B לוקח עד ~3 דקות

# מיפוי: שם כלי → (מפתח ארגומנט, ספק מאולץ או None)
TOOL_MAP = {
    "dev":   ("task",     None),
    "ask":   ("question", None),
    "local": ("prompt",   "local"),
    "cloud": ("prompt",   "cloud"),
}


def _run(prompt: str, provider: str) -> str:
    fn = ask_local if provider == "local" else ask_cloud
    result = fn(prompt)
    return f"[{provider.upper()}]\n\n{result}"


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dev",
            description="משימת פיתוח — מנותבת אוטומטית למקומי או ענן לפי מורכבות",
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_MAP:
        return [TextContent(type="text", text=f"כלי לא מוכר: {name}")]

    arg_key, forced_provider = TOOL_MAP[name]
    prompt = arguments[arg_key]
    provider = forced_provider or route(prompt)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run, prompt, provider),
            timeout=MODEL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        result = f"[{provider.upper()}] שגיאה: פג הזמן לאחר {MODEL_TIMEOUT:.0f} שניות"
    except RuntimeError as e:
        result = f"[{provider.upper()}] שגיאה: {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
