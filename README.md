# local-agent

Your AI runs locally when it can, and in the cloud when it needs to.

local-agent is an MCP server for Claude Code that automatically routes every request to the right place — a free local model on your machine, or Anthropic cloud. You don't decide; it decides for you, based on what the task actually needs and how you've set your priorities. Once installed, it's invisible: it just works.

---

## How routing works

```
You ask Claude Code something
              ↓
        local-agent
       ↙     ↓      ↘
   local   chain    cloud
  (free)  (plan     (only when
          cloud +    needed)
          run local)
```

- **Local** — code generation, refactoring, tests, docs → free, instant
- **Chain** — cloud writes a short implementation plan, local generates the body → near-cloud quality at a fraction of the cost
- **Cloud** — architecture, security review, deep debugging, complex reasoning → only when it matters

Every response includes a header so you always know what ran and where:

```
[LOCAL qwen2.5-coder:14b · 1.8s · score 0.18]
[CLOUD claude-sonnet-4-6 · 3.4s · score 0.81]
[CHAIN claude-sonnet-4-6+qwen2.5-coder:14b · 5.1s · score 0.74]
```

---

## Installation

**Requirements:** Claude Code, Python 3.10+.  
**Optional:** [Ollama](https://ollama.com) — for local models. Without it, everything routes to cloud.

```bash
git clone https://github.com/MrFalach/local-agent.git
cd local-agent
pip install -r requirements.txt
python setup.py
```

The wizard reads your hardware, shows a grouped list of models that fit your machine, and asks at most 4 questions:

1. Global or project-only?
2. Which local model?
3. Priority (quality / cost / speed / balanced)?
4. Anthropic API key (skipped if already set)?

Then it registers the MCP server with Claude Code. Restart Claude Code when done.

---

## Hardware-aware model selection

The wizard reads your RAM and only shows models your machine can run comfortably. Larger models are hidden automatically.

| RAM | Recommended model | Notes |
|-----|-------------------|-------|
| < 8 GB | — | cloud-only mode |
| 8–16 GB | qwen2.5-coder:7b | solid coding model |
| 16–32 GB | qwen2.5-coder:14b | better quality, still fast |
| 32–64 GB | qwen2.5-coder:32b | high quality locally |
| 64 GB+ | qwen2.5-coder:72b | near-cloud quality, free |

> Only one model runs in RAM at a time. Switching costs 20–40s cold-load. Pick the one that covers your main use case and let cloud handle the rest.

---

## Priority — one setting that drives everything

| Priority | Behavior | Best for |
|----------|----------|----------|
| `quality` | goes to cloud easily | important projects, critical code |
| `cost` *(default)* | stays local; cloud only when task is hard | daily work, saving money |
| `speed` | fastest response, chain disabled | quick edits, high volume |
| `balanced` | smart split | general use |

---

## Tools available in Claude Code

| Tool | What it does |
|------|-------------|
| `local-agent:dev` | coding task — auto-routed by complexity |
| `local-agent:ask` | technical question — auto-routed |
| `local-agent:local` | force local model |
| `local-agent:cloud` | force cloud |
| `local-agent:stats` | summary: cloud %, latency p50/p95, estimated cost |

---

## Per-project configuration

To use different settings for a specific project:

```bash
cd ~/your-project
python /path/to/local-agent/setup.py --project
```

This asks 2 questions (priority + model), inherits everything else from your global config, and saves a `.local-agent.json` in the project folder. Claude Code picks it up automatically the next time it starts.

---

## Configuration layers

Settings are merged in priority order — higher overrides lower:

```
environment variables          (LOCAL_AGENT_PRIORITY, LOCAL_MODEL, ...)
  └── .local-agent.json        (project folder — written by setup.py --project)
        └── ~/.claude/local-agent/config.json   (global — written by setup.py)
              └── built-in defaults
```

`ANTHROPIC_API_KEY` is stored in `.env` only, never in JSON config files.

---

## File overview

```
setup.py      interactive setup wizard (hardware detection, model catalog, --project mode)
hardware.py   RAM detection → model tier recommendation
config.py     multi-layer config loader + priority profiles
server.py     MCP server — entry point for Claude Code
router.py     routing logic (score 0..1 from keyword + complexity analysis)
providers.py  Ollama + Anthropic + chain route
telemetry.py  JSONL logging + stats summary
CLAUDE.md     routing instructions embedded for Claude Code itself
```

---

## License

MIT
