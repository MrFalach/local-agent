# local-agent

**Your AI runs locally when it can, and in the cloud when it needs to.**

local-agent sits between you and Claude Code. Every request is automatically sent to the best place — simple coding tasks go to a free local model on your machine, complex questions go to Claude in the cloud. You don't decide; it decides for you.

Once installed, it works automatically in every Claude Code session. No commands to remember.

---

## How it works

```
You ask Claude Code something
              ↓
        local-agent
       ↙     ↓      ↘
   local   chain    cloud
  (free)  (plan    (only when
          cloud +   needed)
          run local)
```

- **Local** — writing code, refactoring, tests, docs → free, instant
- **Cloud** — architecture, deep debugging, security, "why" questions → best quality
- **Chain** — cloud plans in a few lines, local generates the body → quality + savings

Every response starts with a short tag so you always know what happened:
`[LOCAL qwen2.5-coder:14b · 1.8s · score 0.18]` → free, ran locally
`[CLOUD claude-sonnet-4-6 · 3.4s · score 0.81]` → cloud, only the thinking costs

---

## Installation

**Requirements:** Claude Code, Python 3.10+.
**Optional:** [Ollama](https://ollama.com) — for local models (without it, everything goes to cloud).

```bash
git clone https://github.com/MrFalach/local-agent.git
cd local-agent
pip install -r requirements.txt
python setup.py
```

The setup wizard detects your hardware, shows a list of models that fit your machine, asks at most 4 questions, and registers the tool with Claude Code. Restart Claude Code when done — after that, everything is automatic.

---

## Hardware-aware model selection

The wizard reads your RAM and shows only models that will actually run well on your machine. Larger models are hidden — no guessing.

| RAM | Recommended model | Notes |
|-----|-------------------|-------|
| 8–16 GB | qwen2.5-coder:7b | solid coding model |
| 16–32 GB | qwen2.5-coder:14b | better quality, still fast |
| 32–64 GB | qwen2.5-coder:32b | high quality locally |
| 64 GB+ | qwen2.5-coder:72b | near-cloud quality, free |
| < 8 GB | — | cloud-only mode |

The model list is grouped by what's already installed, what's available to download, and what would overlap with something you already have.

> **Tip:** only one model runs in RAM at a time. Switching costs 20–40s cold-load. Pick one that covers your main use case and let cloud handle the rest.

---

## Per-project configuration

Want different settings for a specific project? Run this inside that project's folder:

```bash
cd ~/your-project
python /path/to/local-agent/setup.py --project
```

This asks 2 questions (priority + model), inherits everything else from your global config, and saves a `.local-agent.json` in that folder. Claude Code picks it up automatically.

---

## Priority — the one setting that drives everything

| Priority | Behavior | Best for |
|----------|----------|----------|
| `quality` | goes to cloud easily | important projects, critical code |
| `cost` *(default)* | stays local, cloud only when hard | daily work, saving money |
| `speed` | fastest response, no chain | quick edits, high volume |
| `balanced` | smart split | general use |

---

## Tools available in Claude Code

| Tool | What it does |
|------|-------------|
| `local-agent:dev` | coding task — routed automatically |
| `local-agent:ask` | technical question — routed automatically |
| `local-agent:local` | force local model |
| `local-agent:cloud` | force cloud |
| `local-agent:stats` | summary: cloud share, response times, estimated cost |

---

## Configuration

Settings are layered — higher overrides lower:

```
environment variables
  └── .local-agent.json   (current project folder)
        └── ~/.claude/local-agent/config.json   (global)
              └── built-in defaults
```

The global config is written by `python setup.py`. The project config by `python setup.py --project`. You can also edit either JSON file directly.

`ANTHROPIC_API_KEY` is stored in `.env` only, never in JSON files.

---

## File overview

```
setup.py      interactive setup wizard
hardware.py   detect RAM → recommended model
config.py     multi-layer config + priority profiles
server.py     MCP server (entry point for Claude Code)
router.py     routing logic (score 0..1)
providers.py  Ollama + Anthropic + chain route
telemetry.py  JSONL logging + stats
CLAUDE.md     instructions for Claude Code
```

---

## License

MIT
