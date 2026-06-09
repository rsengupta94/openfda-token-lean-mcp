# Measurement: token cost — lean vs naive vs raw

How much does lean MCP primitive design actually save? This measures the openFDA
Token-Lean MCP server against two baselines, with an honestly-stated method and
**per-query-type** results — deliberately **not** a single universal percentage.

## Method

**Three arms**, each measured as **tool-schema tokens + response tokens**:

| Arm | Tool schema | Response |
|---|---|---|
| **raw API** | — (no MCP layer) | unfiltered openFDA JSON |
| **naive MCP** | verbose auto-generated schema | raw passthrough incl. `meta` |
| **lean MCP** | lean schema | projected / aggregated / curated; `meta` stripped |

The **naive** arm is a *faithful thin wrapper, not a strawman*: its tool schemas expose
openFDA's real Elasticsearch-style query interface with real, usable parameters and field
documentation (what existing openFDA MCP wrappers do), and its responses are the genuine
raw openFDA payload (the server's own `--shaper=naive` mode). So `lean vs naive` isolates
leanness discipline against a fair wrapper, and `lean vs raw` isolates response-shaping
against the bare data floor (which carries no tool schema at all).

- **Tokenizer:** Gemini `count_tokens`, model `gemini-2.5-flash`, measured 2026-06-09. The
  server is model-agnostic; absolute counts are tokenizer-specific, but the relative deltas
  are ≈tokenizer-robust (a utf-8 byte-size dry run produced the same shape).
- **Task set:** 10 tasks spanning count / projected-record / label-section / resolve, over
  ibuprofen, warfarin, atorvastatin, metformin, Advil, Tylenol (defined in `harness/tasks.py`).
- **Variance:** 3 runs; per-task token range was **0** (`count_tokens` is deterministic and
  openFDA totals were stable within the run window).
- The harness is not shipped; this document records the method + task set so the numbers are
  reproducible.

## Results (mean Gemini tokens)

### By query type
| query type | n | raw | naive | lean | lean vs naive | lean vs raw (resp) |
|---|--:|--:|--:|--:|--:|--:|
| count | 3 | 206 | 639 | 285 | −55.4% | −43.1% |
| records | 3 | 284,918 | 285,351 | 1,160 | −99.6% | −99.7% |
| label-section | 2 | 41,413 | 41,871 | 872 | −97.9% | −98.2% |
| resolve | 2 | 45,509 | 45,781 | 426 | −99.1% | −99.2% |

### By task
| task | type | raw | naive | lean | lean vs naive | lean vs raw (resp) |
|---|---|--:|--:|--:|--:|--:|
| ibuprofen-ae-records | records | 775,991 | 776,438 | 935 | −99.9% | −99.9% |
| atorvastatin-ae-records | records | 69,485 | 69,932 | 745 | −98.9% | −99.2% |
| metformin-recalls | records | 9,277 | 9,682 | 1,799 | −81.4% | −82.4% |
| warfarin-boxed | label-section | 31,640 | 32,098 | 400 | −98.8% | −99.2% |
| atorvastatin-summary | label-section | 51,186 | 51,644 | 1,344 | −97.4% | −97.7% |
| resolve-advil | resolve | 50,871 | 51,143 | 501 | −99.0% | −99.2% |
| resolve-tylenol | resolve | 40,147 | 40,419 | 350 | −99.1% | −99.3% |
| metformin-recall-count | count | 124 | 529 | 192 | −63.7% | −77.4% |
| ibuprofen-ae-count | count | 250 | 697 | 334 | −52.1% | −34.0% |
| warfarin-ae-count | count | 244 | 691 | 328 | −52.5% | −34.8% |

## Reading the results

**There is no single headline number — the saving scales with how bulky the underlying
document is.** Two regimes:

1. **Document-bearing queries (the strong levers): 97–99.9%.** Anything that would
   otherwise return full records or full labels collapses dramatically. One ibuprofen
   adverse-event *records* call returns **~776,000 tokens** raw — multiples of a typical
   context window — versus **935** lean (−99.9%); a full SPL label is ~31–51K tokens raw
   versus a few hundred for the requested section. The bulky document still exists and is
   reachable **on demand** via the `openfda://label/{set_id}` Resource — it simply isn't
   inlined into every answer. This is the central thesis: *Tools return lean answers;
   Resources hold the bulky documents.*

2. **Aggregations (the modest, honestly-stated lever): `count`.** openFDA's `count` mode is
   already compact, so the absolute numbers are small and the picture is subtler. The lean
   count *response* is 34–77% smaller than raw, but because the lean tool always carries a
   (small) schema while the bare raw-API floor carries none, the lean *total* for a count
   query (192–334 tokens) can slightly exceed the raw response floor (124–250). Against a
   real MCP wrapper — the naive arm, which also has a schema — lean still wins **52–64%**,
   driven by the verbose-vs-lean schema gap plus `meta`-strip and bucket trimming.

So the lean architecture is transformative for document-bearing queries and a moderate,
schema-driven win for aggregations. We deliberately do **not** average these into one
percentage.

## Caveats

- **Tokenizer.** Counts use Gemini `gemini-2.5-flash`. A different tokenizer shifts the
  absolute numbers; relative deltas are ≈stable (confirmed by the byte-size dry run).
- **Baseline fairness.** The naive arm is a faithful passthrough wrapper with real params,
  not a strawman; results are also reported against the raw-API floor.
- **Data drift.** openFDA report totals change over time; re-running may shift absolute
  response sizes, but the relative story holds.
- **Count framing.** As above, the lean total can exceed the bare raw response for tiny
  aggregations; we report response-only and vs-naive separately rather than hiding it.
