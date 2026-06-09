"""Tool params -> openFDA query syntax, with input validation.

This module is the security quality bar. User-supplied text is treated as **data**,
never as query syntax: every term is length-checked, control-char-screened, escaped,
and wrapped in a quoted phrase literal, so it cannot inject openFDA/Lucene operators
or select arbitrary fields. Field and aggregation names come only from the allowlists
in `fields.py`.
"""

from __future__ import annotations

from .fields import (
    COUNT_FIELDS,
    DRUG_QUERY_FIELD,
    DRUG_QUERY_FIELD_BRAND,
    ENDPOINTS,
    MAX_LIMIT,
    MAX_SKIP,
)

MAX_TERM_LEN = 200


class QueryError(ValueError):
    """A tool argument failed validation (safe to surface to the caller)."""


def validate_endpoint(endpoint: str) -> str:
    if endpoint not in ENDPOINTS:
        raise QueryError(
            f"unknown endpoint {endpoint!r}; expected one of {sorted(ENDPOINTS)}"
        )
    return endpoint


def _escape(term: str) -> str:
    # Backslash first, then the double-quote that closes the phrase literal.
    return term.replace("\\", "\\\\").replace('"', '\\"')


def quote_term(term: str) -> str:
    """Validate and escape a user term, returning a quoted phrase literal."""
    if not isinstance(term, str):
        raise QueryError("search term must be a string")
    t = term.strip()
    if not t:
        raise QueryError("search term is empty")
    if len(t) > MAX_TERM_LEN:
        raise QueryError(f"search term too long ({len(t)} > {MAX_TERM_LEN})")
    if any(ord(c) < 0x20 for c in t):
        raise QueryError("search term contains control characters")
    return f'"{_escape(t)}"'


def build_drug_search(endpoint: str, term: str, *, include_brand: bool = False) -> str:
    """Build a validated `search` expression matching a drug name on `endpoint`."""
    validate_endpoint(endpoint)
    phrase = quote_term(term)
    clause = f"{DRUG_QUERY_FIELD[endpoint]}:{phrase}"
    if include_brand:
        clause = f"({clause} OR {DRUG_QUERY_FIELD_BRAND[endpoint]}:{phrase})"
    return clause


def resolve_count_field(endpoint: str, key: str) -> str:
    """Map a friendly count_by key to its (allowlisted) openFDA count field."""
    validate_endpoint(endpoint)
    table = COUNT_FIELDS.get(endpoint, {})
    if key not in table:
        raise QueryError(
            f"cannot count by {key!r} on {endpoint!r}; available: {sorted(table)}"
        )
    return table[key]


def validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise QueryError("limit must be an integer")
    if not 1 <= limit <= MAX_LIMIT:
        raise QueryError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit


def validate_skip(skip: int) -> int:
    if not isinstance(skip, int) or isinstance(skip, bool):
        raise QueryError("skip must be an integer")
    if not 0 <= skip <= MAX_SKIP:
        raise QueryError(f"skip must be between 0 and {MAX_SKIP}")
    return skip
