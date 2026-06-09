"""openFDA endpoint + field maps.

Field paths were verified LIVE against https://api.fda.gov on 2026-06-09
(see spec.md verification log). Lean projection/curation happens client-side in the
shaper (Phase 1); this module only names the fields the query layer searches and
aggregates on.
"""

BASE_URL = "https://api.fda.gov"

# friendly endpoint key -> API path segment
ENDPOINTS = {
    "event": "drug/event",
    "label": "drug/label",
    "enforcement": "drug/enforcement",
}

# Field a drug-name query searches, per endpoint. We target the normalized `openfda`
# annotation (clean aggregation) rather than raw free-text product names.
DRUG_QUERY_FIELD = {
    "event": "patient.drug.openfda.generic_name",
    "label": "openfda.generic_name",
    "enforcement": "openfda.generic_name",
}
DRUG_QUERY_FIELD_BRAND = {
    "event": "patient.drug.openfda.brand_name",
    "label": "openfda.brand_name",
    "enforcement": "openfda.brand_name",
}

# count_by friendly key -> ready-to-use openFDA count field.
#
# openFDA disables aggregation on analyzed text fields, so EVERY count field must use
# the `.exact` keyword sub-field — even keyword-looking enums like classification/status.
# Confirmed live 2026-06-09: `count=classification` -> HTTP 500 ("Text fields are not
# optimised for ... aggregations"); `count=classification.exact` -> 200.
COUNT_FIELDS = {
    "event": {
        "reaction": "patient.reaction.reactionmeddrapt.exact",
    },
    "label": {
        "route": "openfda.route.exact",
    },
    "enforcement": {
        "classification": "classification.exact",  # Class I/II/III
        "status": "status.exact",                   # Ongoing/Completed/Terminated
        "reason": "reason_for_recall.exact",
    },
}

# openFDA hard caps (the API rejects values above these).
MAX_LIMIT = 1000
MAX_SKIP = 25000
