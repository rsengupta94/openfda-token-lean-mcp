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

How you invoke a primitive depends on the client:

- **Claude Desktop / Claude Code (a model is in the loop):** ask in plain language — _"top adverse reactions for ibuprofen"_, _"boxed warning for warfarin"_ — and the model fills in the arguments below for you.
- **MCP Inspector or any direct MCP client (no model):** you supply the arguments yourself in a form. There is no natural-language step — that's expected.

The server exposes **4 tools, 2 resource templates, and 1 prompt.**

### Tools

Each tool returns a lean JSON payload. `query`/`term` is always required.

#### `search_adverse_events(query, count_by=None, fields=None, limit=10)`
Adverse-event (FAERS) reports for a drug.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | _required_ | Drug **generic** name. Matches the normalized generic name, so use `ibuprofen`, not `Advil`. |
| `count_by` | string | `null` | `"reaction"` → ranked reaction counts. Omit for projected records. |
| `fields` | string[] | `null` | Record mode only — replace the default projection with these top-level fields (see the fields catalog resource). |
| `limit` | integer | `10` | 1–1000. Number of count buckets, or number of records. |

Returns — **count mode:** `{ drug, total_reports, top: [{value, count}] }`; **record mode:** `{ results: [{report_id, received, serious, drugs[], reactions[]}] }`.

```jsonc
// search_adverse_events(query="ibuprofen", count_by="reaction", limit=5)
{ "drug": "ibuprofen", "total_reports": 279646,
  "top": [ {"value": "DRUG INEFFECTIVE", "count": 27091}, {"value": "PAIN", "count": 19276} ] }
```

#### `search_drug_labels(query, sections=["summary"], limit=5)`
Curated sections of a drug's SPL label.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | _required_ | Drug **brand or generic** name. |
| `sections` | string[] | `["summary"]` | SPL section names — e.g. `boxed_warning`, `indications_and_usage`, `warnings`, `adverse_reactions`, `contraindications`, `dosage_and_administration`, `drug_interactions` — or `"summary"` for a compact curated set. Sections absent on a label are simply omitted. |
| `limit` | integer | `5` | 1–1000. Max matching labels to return. |

Returns: `{ results: [{drug, set_id, <each requested section>}] }`. **Always includes `set_id`** — the handle for the full-label resource below.

#### `search_recalls(query, count_by=None, fields=None, limit=10)`
Drug enforcement (recall) reports for a drug.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | _required_ | Drug **brand or generic** name (matches the recall's drug, not the firm). |
| `count_by` | string | `null` | `"classification"`, `"status"`, or `"reason"` → ranked counts. Omit for projected records. |
| `fields` | string[] | `null` | Record mode only — replace the default projection. |
| `limit` | integer | `10` | 1–1000. Buckets or records. |

Returns — **count mode:** `{ drug, top: [{value, count}] }`; **record mode:** `{ results: [{recall_number, status, classification, reason, product, firm, date}] }`.

#### `resolve_drug(term)`
Map a brand or generic name to identifiers.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `term` | string | _required_ | A brand or generic name, e.g. `Advil`. |

Returns: `{ query, generic_name, brand_names[], product_ndc[], rxcui[] }` — or `{ query, candidates[] }` when the name is ambiguous or absent from current openFDA labels.

### Resource templates

Read by URI via MCP `resources/read`. An MCP client or coding agent (the Inspector, Claude Code, an SDK) reads them by URI directly; in a chat host, ask for the document and the host fetches it.

| URI template | Parameter | Returns |
|---|---|---|
| `openfda://label/{set_id}` | `set_id` — copied from a `search_drug_labels` result | The full SPL label document (the bulky doc, on demand). |
| `openfda://fields/{endpoint}` | `endpoint` = `event` \| `label` \| `enforcement` | The projectable-field catalog for that endpoint — each field's `name`/`type` and any `count_by` key. Feed field names to a tool's `fields` parameter. |

**Fetching a full label — the two-step handoff.** You never supply `set_id` yourself; a tool hands it to you:

```
1. search_drug_labels(query="warfarin", sections=["boxed_warning"])
     → { "drug": "WARFARIN SODIUM", "set_id": "0cbce382-…", "boxed_warning": [ … ] }   (~1 KB)

2. read  openfda://label/0cbce382-…
     → the full SPL label document                                                      (~130 KB)
```

### Prompt

| Prompt | Parameter | What it does |
|---|---|---|
| `drug_safety_review` | `drug_name` (string) | Returns a guided workflow that assembles the boxed warning, most-reported serious adverse events, and active recalls for the drug. Appears in hosts as a reusable prompt / slash-command. |

## Notes

- **Modes:** ships lean by default. `--shaper naive` switches to raw passthrough — the
  measurement control, for reproducing the numbers, not for production use.
- **Rate limits:** openFDA is keyless. Set `OPENFDA_API_KEY` to raise the daily cap from
  1,000 to 120,000 requests.
- **Data:** [openFDA](https://open.fda.gov) (`api.fda.gov`). Not affiliated with or endorsed
  by the FDA; openFDA data is for research and informational use, not clinical
  decision-making.
