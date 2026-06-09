"""Phase 0 done-state check (LIVE).

Runs a validated search and a count aggregation against all three openFDA drug
endpoints, shows an unknown drug returning a graceful empty, and shows invalid input
rejected with a clear error. Requires network access to https://api.fda.gov.

    uv run python scripts/smoke.py
"""

import asyncio

from openfda_lean_mcp.client import OpenFDAClient
from openfda_lean_mcp.query import (
    QueryError,
    build_drug_search,
    resolve_count_field,
    validate_limit,
)

DRUG = "ibuprofen"


async def main() -> None:
    async with OpenFDAClient() as c:
        print("== validated search, all three endpoints ==")
        for ep in ("event", "label", "enforcement"):
            search = build_drug_search(ep, DRUG, include_brand=(ep == "enforcement"))
            r = await c.search(ep, search=search, limit=validate_limit(1))
            total = (r["meta"].get("results") or {}).get("total")
            print(f"  {ep:12s} results={len(r['results'])}  meta.total={total}")

        print("== count aggregation ==")
        rx = await c.count(
            "event",
            resolve_count_field("event", "reaction"),
            search=build_drug_search("event", DRUG),
            limit=3,
        )
        print("  event reactions top3:", [(x["term"], x["count"]) for x in rx["results"][:3]])

        rc = await c.count(
            "enforcement",
            resolve_count_field("enforcement", "classification"),
            search=build_drug_search("enforcement", DRUG, include_brand=True),
        )
        print("  enforcement classification:", [(x["term"], x["count"]) for x in rc["results"]])

        print("== unknown drug -> graceful empty ==")
        empty = await c.search("label", search=build_drug_search("label", "zzzznotadrugzzzz"), limit=1)
        print("  results:", len(empty["results"]))

    print("== invalid input rejected ==")
    for label, fn in (
        ("empty term", lambda: build_drug_search("label", "   ")),
        ("bad limit", lambda: validate_limit(99999)),
        ("bad count_by", lambda: resolve_count_field("event", "nope")),
    ):
        try:
            fn()
            print(f"  {label}: NOT REJECTED (bug)")
        except QueryError as e:
            print(f"  {label}: rejected -> {e}")


if __name__ == "__main__":
    asyncio.run(main())
