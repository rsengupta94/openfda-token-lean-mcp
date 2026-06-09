# openFDA Token-Lean MCP Server

**A [Model Context Protocol](https://modelcontextprotocol.io) server for the openFDA drug
API that returns the _answer_, not the raw document dump.** Its tools hand an LLM curated,
aggregated results — orders of magnitude fewer tokens than the raw API — while full
documents stay one resource fetch away.

Model-agnostic · runs on any MCP host over stdio · zero LLM/runtime dependency.

## Why

openFDA returns enormous payloads. A single adverse-event query can exceed **700,000
tokens** of nested FAERS JSON; a drug label runs 30–50k tokens of free text. A thin
passthrough wrapper forwards all of it into the model's context to answer a one-line
question — overflowing the context window, inflating cost, and slowing every call.

This server applies one rule:

> **Tools return lean answers. Resources hold the bulky documents.**

Each tool projects, aggregates, or curates the response and strips openFDA's repeated
`meta` boilerplate. The full document isn't lost — it stays one `openfda://label/{set_id}`
fetch away, retrieved only when it's actually needed (progressive disclosure).

## What it saves

Measured with Gemini `count_tokens` over a fixed task set — same question, this server vs.
a faithful naive passthrough wrapper. Full method, per-task numbers, the raw-API floor, and
caveats are in [`MEASUREMENT.md`](./MEASUREMENT.md).

| Query | Naive wrapper | Lean (this) | Reduction |
|---|--:|--:|--:|
| Adverse-event records | 285,351 | 1,160 | **−99.6%** |
| Label section | 41,871 | 872 | **−97.9%** |
| Drug resolution | 45,781 | 426 | **−99.1%** |
| Reaction counts | 639 | 285 | **−55%** |

A single _"adverse events for ibuprofen"_ request is **775,991 tokens** of raw FAERS JSON —
larger than most context windows. This server answers it in **935**.

Savings scale with document size: largest for queries that would otherwise return full
records or labels, smaller but real for openFDA's already-compact `count` aggregations.
There is no single universal figure — read the per-type numbers, honestly, in
[`MEASUREMENT.md`](./MEASUREMENT.md).

## Install & connect

Requires [`uv`](https://docs.astral.sh/uv/). The server speaks MCP over stdio.

**Run it** (directly from this repo, no clone):

```sh
uvx --from git+https://github.com/rsengupta94/openfda-token-lean-mcp openfda-lean-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`, then restart:

```json
{
  "mcpServers": {
    "openfda-lean": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/rsengupta94/openfda-token-lean-mcp", "openfda-lean-mcp"]
    }
  }
}
```

**Claude Code:**

```sh
claude mcp add openfda-lean -- uvx --from git+https://github.com/rsengupta94/openfda-token-lean-mcp openfda-lean-mcp
```

**Develop / inspect locally:**

```sh
git clone https://github.com/rsengupta94/openfda-token-lean-mcp
cd openfda-token-lean-mcp && uv sync
npx @modelcontextprotocol/inspector uv run openfda-lean-mcp   # browser UI
uv run pytest                                                 # tests
```

## Using it

Once connected, drive it in natural language — the host's model picks the tool. Agents and
MCP clients can also call the tools and read the resources directly.

### Tools

| Ask | Tool call | Returns |
|---|---|---|
| "Top adverse reactions for ibuprofen" | `search_adverse_events(query, count_by="reaction")` | ranked reaction counts |
| "Adverse-event reports for ibuprofen" | `search_adverse_events(query, limit=10)` | projected FAERS records |
| "Boxed warning for warfarin" | `search_drug_labels(query, sections=["boxed_warning"])` | that section only, plus `set_id` |
| "Summarize the atorvastatin label" | `search_drug_labels(query, sections=["summary"])` | curated section subset, plus `set_id` |
| "Recalls for metformin" | `search_recalls(query, limit=10)` | projected recall records |
| "Recall classifications for metformin" | `search_recalls(query, count_by="classification")` | ranked counts |
| "Generic name for Advil" | `resolve_drug(term)` | generic name, brands, NDC, RxCUI (or candidates if ambiguous) |

- **`sections`** — any SPL section (`boxed_warning`, `indications_and_usage`, `warnings`, `adverse_reactions`, …) or `"summary"` (a compact curated set). Default: `summary`.
- **`count_by`** — `reaction` for events; `classification` / `status` / `reason` for recalls. Omit it to get projected records instead of counts.
- **`fields`** — overrides the default record projection (see *Discovering fields* below).

A lean response — `search_adverse_events(query="ibuprofen", count_by="reaction")`:

```json
{
  "drug": "ibuprofen",
  "total_reports": 279646,
  "top": [
    { "value": "DRUG INEFFECTIVE", "count": 27091 },
    { "value": "PAIN", "count": 19276 }
  ]
}
```

### Fetching a full document

By design, **no tool inlines a full label** — that is the token saving. `search_drug_labels`
always returns a `set_id`, and the complete Structured Product Label is one resource read
away:

```
1.  search_drug_labels(query="warfarin", sections=["boxed_warning"])
       → { "drug": "WARFARIN SODIUM", "set_id": "0cbce382-…", "boxed_warning": [ … ] }   (~1 KB)

2.  read resource:  openfda://label/0cbce382-…
       → the full SPL label document                                                     (~130 KB)
```

This uses MCP's standard `resources/read`. A coding agent or MCP client — Claude Code, the
MCP Inspector, or any SDK client — reads the URI directly; in a chat host, ask for the full
label and the host fetches the resource. The lean answer stays cheap; the full document is
there the moment you actually need it.

### Discovering fields

Read `openfda://fields/{endpoint}` (`endpoint` = `event` | `label` | `enforcement`) for the
catalog of projectable fields, then pass field names to a tool's `fields` parameter to
tailor the projected records.

### Guided review

The `drug_safety_review(drug_name)` prompt expands into a workflow that assembles the boxed
warning, the most-reported serious adverse events, and active recalls — surfaced in hosts as
a reusable prompt / slash-command.

## Notes

- **Modes:** ships lean by default. `--shaper naive` switches to raw passthrough — the
  measurement control, for reproducing the numbers, not for production use.
- **Rate limits:** openFDA is keyless. Set `OPENFDA_API_KEY` to raise the daily cap from
  1,000 to 120,000 requests.
- **Data:** [openFDA](https://open.fda.gov) (`api.fda.gov`). Not affiliated with or endorsed
  by the FDA; openFDA data is for research and informational use, not clinical
  decision-making.
