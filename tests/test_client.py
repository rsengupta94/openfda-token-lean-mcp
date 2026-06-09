import pytest

from openfda_lean_mcp.client import OpenFDAError, _parse


def test_parse_search_ok():
    out = _parse(200, {"results": [{"a": 1}], "meta": {"results": {"total": 5}}})
    assert out["results"] == [{"a": 1}]
    assert out["meta"]["results"]["total"] == 5


def test_parse_count_shape():
    out = _parse(200, {"results": [{"term": "NAUSEA", "count": 10}], "meta": {}})
    assert out["results"][0]["term"] == "NAUSEA"
    assert out["results"][0]["count"] == 10


def test_parse_not_found_is_graceful_empty():
    body = {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
    out = _parse(404, body)
    assert out["results"] == []


def test_parse_other_errors_raise():
    with pytest.raises(OpenFDAError):
        _parse(500, None)
    with pytest.raises(OpenFDAError):
        _parse(400, {"error": {"code": "BAD_REQUEST"}})
    with pytest.raises(OpenFDAError):
        _parse(403, {"error": {"code": "OVER_RATE_LIMIT"}})
