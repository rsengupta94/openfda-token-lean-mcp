import pytest

from openfda_lean_mcp.query import (
    QueryError,
    build_drug_search,
    quote_term,
    resolve_count_field,
    validate_endpoint,
    validate_limit,
    validate_skip,
)


def test_quote_term_basic():
    assert quote_term("ibuprofen") == '"ibuprofen"'
    assert quote_term("  ibuprofen  ") == '"ibuprofen"'  # trimmed


def test_quote_term_escapes_operators():
    # Embedded quotes/backslashes are escaped so they can't break out of the literal.
    assert quote_term('say "hi"') == '"say \\"hi\\""'
    assert quote_term("a\\b") == '"a\\\\b"'


@pytest.mark.parametrize("bad", ["", "   ", "x" * 201, "a\x00b", 123, None])
def test_quote_term_rejects(bad):
    with pytest.raises(QueryError):
        quote_term(bad)


def test_build_drug_search():
    assert build_drug_search("label", "ibuprofen") == 'openfda.generic_name:"ibuprofen"'
    assert (
        build_drug_search("event", "ibuprofen")
        == 'patient.drug.openfda.generic_name:"ibuprofen"'
    )


def test_build_drug_search_with_brand():
    assert build_drug_search("enforcement", "advil", include_brand=True) == (
        '(openfda.generic_name:"advil" OR openfda.brand_name:"advil")'
    )


def test_unknown_endpoint_rejected():
    with pytest.raises(QueryError):
        validate_endpoint("device")
    with pytest.raises(QueryError):
        build_drug_search("device", "x")


def test_resolve_count_field():
    assert resolve_count_field("event", "reaction") == "patient.reaction.reactionmeddrapt.exact"
    assert resolve_count_field("enforcement", "classification") == "classification.exact"
    with pytest.raises(QueryError):
        resolve_count_field("event", "nope")


@pytest.mark.parametrize("n", [0, -1, 1001, 1.5, True, "10"])
def test_validate_limit_rejects(n):
    with pytest.raises(QueryError):
        validate_limit(n)


def test_validate_limit_ok():
    assert validate_limit(1) == 1
    assert validate_limit(1000) == 1000


@pytest.mark.parametrize("n", [-1, 25001, 2.0, True])
def test_validate_skip_rejects(n):
    with pytest.raises(QueryError):
        validate_skip(n)


def test_validate_skip_ok():
    assert validate_skip(0) == 0
    assert validate_skip(25000) == 25000
