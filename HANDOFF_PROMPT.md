Bachbot project at /Volumes/VIXinSSD/bachbot.

Run /trimtab to identify highest-leverage work, then execute continuously using
autocoding workflow. Use Codex MCP for backend/infra tasks. Check Linear issues
for tracked work (`project:Bachbot`). Verify everything with `python3 -m pytest -q`
and `python3 -m bachbot benchmark run --sample 10`.

The critical gap: LLM analysis is dry-run only — get real API calls working via
`bachbot/llm/wrappers.py` (already has httpx OpenAI-compatible execution). The
composition engine works (358/358 chorales) but chord variety is 4.3 vs Bach's
14.7 and 21/30 chorales have parallel octaves. Fix these.

See memory files for full context. All 51 tests must stay green.
