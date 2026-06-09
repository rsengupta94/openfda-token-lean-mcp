"""Response shaper — the lean product thesis, as pure functions.

Each ``lean_*`` function turns a raw openFDA result set into a lean answer (field
projection / aggregation relabel / label-section curation), dropping ``meta`` and every
field the answer doesn't need. ``naive_passthrough`` is the control: it returns the raw
client output untouched (full records + ``meta``). No I/O here, so it is all unit-testable
offline; the server (and Phase 2 harness) wire these onto live data.

Output shapes follow the interface contracts in spec.md.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Curated "summary" = a compact, high-signal subset of label sections (only those
# present on a given label are emitted; OTC monograph labels often lack boxed_warning).
SUMMARY_SECTIONS: tuple[str, ...] = (
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "warnings",
)


def naive_passthrough(raw: dict[str, Any]) -> dict[str, Any]:
    """Control mode: raw openFDA ``{results, meta}`` with no shaping."""
    return raw


def _first(value: Any) -> Any:
    """openFDA stores most label/openfda values as single-element lists."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def project(results: list[dict], fields: list[str]) -> list[dict]:
    """Generic top-level projection (the `fields` override on record tools)."""
    return [{k: r.get(k) for k in fields} for r in results]


# --- adverse events (drug/event) ---

def lean_event_counts(drug: str, total_reports: int, buckets: list[dict]) -> dict:
    """count mode -> ranked aggregation (openFDA `term` relabelled to `value`)."""
    return {
        "drug": drug,
        "total_reports": total_reports,
        "top": [{"value": b.get("term"), "count": b.get("count")} for b in buckets],
    }


def lean_event_records(results: list[dict]) -> list[dict]:
    """record mode -> projected reports, dropping the nested openfda cross-refs."""
    out: list[dict] = []
    for r in results:
        patient = r.get("patient") or {}
        drugs: list[str] = []
        for d in patient.get("drug") or []:
            name = d.get("medicinalproduct") or _first((d.get("openfda") or {}).get("generic_name"))
            if name and name not in drugs:
                drugs.append(name)
        reactions = [
            rx.get("reactionmeddrapt")
            for rx in patient.get("reaction") or []
            if rx.get("reactionmeddrapt")
        ]
        out.append(
            {
                "report_id": r.get("safetyreportid"),
                "received": r.get("receivedate"),
                "serious": r.get("serious"),
                "drugs": drugs,
                "reactions": reactions,
            }
        )
    return out


# --- labels (drug/label) ---

def lean_labels(results: list[dict], sections: list[str]) -> list[dict]:
    """Return only the requested sections per match; always include set_id."""
    wanted = list(SUMMARY_SECTIONS) if sections == ["summary"] else sections
    out: list[dict] = []
    for r in results:
        openfda = r.get("openfda") or {}
        item: dict[str, Any] = {
            "drug": _first(openfda.get("generic_name")) or _first(openfda.get("brand_name")),
            "set_id": r.get("set_id"),
        }
        for sec in wanted:
            if sec in r:
                item[sec] = r[sec]
        out.append(item)
    return out


# --- recalls (drug/enforcement) ---

def lean_recalls(results: list[dict]) -> list[dict]:
    return [
        {
            "recall_number": r.get("recall_number"),
            "status": r.get("status"),
            "classification": r.get("classification"),
            "reason": r.get("reason_for_recall"),
            "product": r.get("product_description"),
            "firm": r.get("recalling_firm"),
            "date": r.get("recall_initiation_date"),
        }
        for r in results
    ]


def lean_counts(buckets: list[dict]) -> list[dict]:
    """Shared ranked-bucket relabel (term -> value) for count mode on any endpoint."""
    return [{"value": b.get("term"), "count": b.get("count")} for b in buckets]


# --- resolve_drug ---

def lean_resolve(query: str, results: list[dict]) -> dict:
    """Map a term to identifiers via the label `openfda` block.

    Resolves to the *modal* generic name (e.g. "Advil" -> IBUPROFEN, even though the
    brand spans many ibuprofen formulations). Only when there is no dominant generic —
    a tie at the top — does it return candidates rather than silently pick one.
    """
    generics = [
        g
        for r in results
        if (g := _first((r.get("openfda") or {}).get("generic_name")))
    ]
    if not generics:
        return {"query": query, "candidates": []}

    ranked = Counter(generics).most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return {"query": query, "candidates": [g for g, _ in ranked]}

    primary = ranked[0][0]

    def collect(field: str) -> list[str]:
        vals: list[str] = []
        for r in results:
            if _first((r.get("openfda") or {}).get("generic_name")) != primary:
                continue
            for v in (r.get("openfda") or {}).get(field) or []:
                if v not in vals:
                    vals.append(v)
        return vals

    return {
        "query": query,
        "generic_name": primary,
        "brand_names": collect("brand_name"),
        "product_ndc": collect("product_ndc"),
        "rxcui": collect("rxcui"),
    }
