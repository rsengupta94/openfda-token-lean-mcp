# openFDA Token-Lean MCP Server

A **token-lean, model-agnostic** [MCP](https://modelcontextprotocol.io) server over the
openFDA **drug** API (adverse events, labels, recalls).

**Thesis:** Tools return lean, curated, or aggregated answers; bulky full documents live
behind Resources, fetched by URI only on explicit demand.

The server has **zero LLM/runtime dependency** — it speaks MCP over stdio and calls
openFDA over HTTPS, so it runs on any MCP host. A separate (not-shipped) harness measures
the token before/after with a single native tokenizer (Gemini); relative deltas are
≈tokenizer-robust.

> **Status:** under construction. Phase 0 (data layer) complete; lean MCP server (Tools / Resources / Prompts) next.

Data source: openFDA, base `https://api.fda.gov/` (keyless; a free API key raises the
daily cap). Not affiliated with or endorsed by the FDA.
