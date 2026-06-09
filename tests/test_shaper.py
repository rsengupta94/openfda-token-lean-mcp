"""Offline tests for the lean shaper, using fixtures shaped like real openFDA records
(field names verified live against api.fda.gov)."""

from openfda_lean_mcp import shaper


def test_lean_event_counts_relabels_term_to_value():
    buckets = [{"term": "NAUSEA", "count": 100}, {"term": "DIZZINESS", "count": 50}]
    out = shaper.lean_event_counts("IBUPROFEN", 48213, buckets)
    assert out == {
        "drug": "IBUPROFEN",
        "total_reports": 48213,
        "top": [{"value": "NAUSEA", "count": 100}, {"value": "DIZZINESS", "count": 50}],
    }


def test_lean_event_records_projects_and_drops_openfda():
    raw = [
        {
            "safetyreportid": "123",
            "receivedate": "20230101",
            "serious": "1",
            "patient": {
                "reaction": [{"reactionmeddrapt": "NAUSEA"}, {"reactionmeddrapt": "RASH"}],
                "drug": [
                    {"medicinalproduct": "IBUPROFEN", "openfda": {"generic_name": ["IBUPROFEN"]}},
                    {"openfda": {"generic_name": ["ASPIRIN"]}},  # no medicinalproduct -> fall back
                ],
            },
        }
    ]
    assert shaper.lean_event_records(raw) == [
        {
            "report_id": "123",
            "received": "20230101",
            "serious": "1",
            "drugs": ["IBUPROFEN", "ASPIRIN"],
            "reactions": ["NAUSEA", "RASH"],
        }
    ]


def test_lean_labels_curates_requested_section_only():
    raw = [
        {
            "set_id": "abc-123",
            "openfda": {"generic_name": ["IBUPROFEN"], "brand_name": ["ADVIL"]},
            "boxed_warning": ["serious warning"],
            "indications_and_usage": ["pain"],
            "adverse_reactions": ["a very long section we do NOT want"],
        }
    ]
    out = shaper.lean_labels(raw, ["boxed_warning"])
    assert out == [{"drug": "IBUPROFEN", "set_id": "abc-123", "boxed_warning": ["serious warning"]}]
    # the bulky unrequested section is gone
    assert "adverse_reactions" not in out[0]


def test_lean_labels_summary_expands_to_curated_subset():
    raw = [
        {
            "set_id": "x",
            "openfda": {"generic_name": ["IBUPROFEN"]},
            "indications_and_usage": ["pain"],
            "warnings": ["w"],
            # boxed_warning + dosage absent (e.g. OTC) -> simply omitted, no error
        }
    ]
    out = shaper.lean_labels(raw, ["summary"])
    assert out[0]["set_id"] == "x"
    assert out[0]["indications_and_usage"] == ["pain"]
    assert out[0]["warnings"] == ["w"]
    assert "boxed_warning" not in out[0]


def test_lean_recalls_projection():
    raw = [
        {
            "recall_number": "D-123",
            "status": "Ongoing",
            "classification": "Class II",
            "reason_for_recall": "contamination",
            "product_description": "Ibuprofen 200mg",
            "recalling_firm": "Acme",
            "recall_initiation_date": "20230101",
            "more_noise": "dropped",
        }
    ]
    assert shaper.lean_recalls(raw) == [
        {
            "recall_number": "D-123",
            "status": "Ongoing",
            "classification": "Class II",
            "reason": "contamination",
            "product": "Ibuprofen 200mg",
            "firm": "Acme",
            "date": "20230101",
        }
    ]


def test_lean_resolve_single():
    raw = [
        {
            "openfda": {
                "generic_name": ["IBUPROFEN"],
                "brand_name": ["ADVIL", "MOTRIN"],
                "product_ndc": ["0573-0150"],
                "rxcui": ["5640"],
            }
        }
    ]
    out = shaper.lean_resolve("advil", raw)
    assert out["generic_name"] == "IBUPROFEN"
    assert out["brand_names"] == ["ADVIL", "MOTRIN"]
    assert out["product_ndc"] == ["0573-0150"]
    assert out["rxcui"] == ["5640"]


def test_lean_resolve_ambiguous_returns_candidates():
    raw = [
        {"openfda": {"generic_name": ["IBUPROFEN"]}},
        {"openfda": {"generic_name": ["IBUPROFEN LYSINE"]}},
    ]
    out = shaper.lean_resolve("ibuprofen", raw)
    assert out["candidates"] == ["IBUPROFEN", "IBUPROFEN LYSINE"]
    assert "generic_name" not in out


def test_lean_resolve_empty():
    assert shaper.lean_resolve("zzz", []) == {"query": "zzz", "candidates": []}


def test_naive_passthrough_is_identity():
    raw = {"results": [{"a": 1}], "meta": {"disclaimer": "..."}}
    assert shaper.naive_passthrough(raw) is raw
