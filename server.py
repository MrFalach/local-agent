"""
שרת MCP — ניתוב אוטומטי בין מודל מקומי לענן.

כלים חשופים לקלוד קוד:
  dev(task)  — משימת פיתוח כללית, מנותבת אוטומטית
  ask(question) — שאלה טכנית, מנותבת אוטומטית
  local(prompt) — כפה שימוש במודל מקומי
  cloud(prompt) — כפה שימוש בענן
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from router import route
from providers import ask_local, ask_cloud

app = Server("local-agent")


def _run(prompt: str, provider: str) -> str:
    fn = ask_local if provider == "local" else ask_cloud
    result = fn(prompt)
    return f"[{provider.upper()}]\n\n{result}"


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dev",
            description="משימת פיתוח — מנותבת אוטומטית למודל מקומי או ענן לפי מורכבות",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "תיאור המשימה"},
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="ask",
            description="שאלה טכנית — מנותבת אוטומטית",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="local",
            description="שלח פרומפט ישירות למודל המקומי (בלי ניתוב)",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="cloud",
            description="שלח פרומפט ישירות לקלוד בענן (בלי ניתוב)",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "dev":
        prompt = arguments["task"]
        provider = route(prompt)
    elif name == "ask":
        prompt = arguments["question"]
        provider = route(prompt)
    elif name == "local":
        prompt = arguments["prompt"]
        provider = "local"
    elif name == "cloud":
        prompt = arguments["prompt"]
        provider = "cloud"
    else:
        return [TextContent(type="text", text=f"כלי לא מוכר: {name}")]

    result = await asyncio.to_thread(_run, prompt, provider)
    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
