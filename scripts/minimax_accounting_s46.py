"""Conservative monitoring for M3's observed but undocumented `default` echo.

Do not assert default == standard. For a captured explicit-standard M3 request,
use the higher published short-context priority rate when the response says
default. This is an estimate, not a verified tier, invoice or hard cost bound.
"""

from copy import deepcopy
from benchmark import usage_s39 as usage

PRIORITY_RATES = {"input_per_million": 0.45, "output_per_million": 1.8}


def account(raw, spec, payload=None):
    original = usage.account(raw, spec)
    if (original["status"] != "unknown" or spec.get("provider") != "minimax"
            or spec.get("model") != "MiniMax-M3" or not isinstance(raw, dict)
            or raw.get("model") != "MiniMax-M3" or raw.get("service_tier") != "default"
            or not isinstance(payload, dict) or payload.get("model") != "MiniMax-M3"
            or payload.get("service_tier") != "standard"):
        return original
    pricing_view = deepcopy(raw)
    pricing_view["service_tier"] = "standard"  # Only the old estimator's scope guard; never edits capture.
    conservative = usage.account(pricing_view, {**spec, **PRIORITY_RATES})
    if conservative["status"] == "unknown":
        return original
    return {**conservative,
        "tier_status": "unverified_default_response_to_explicit_standard_request",
        "monitoring_policy": "higher_published_short_context_priority_rates_no_cache_discount",
        "rates_per_million": PRIORITY_RATES,
        "invoice_or_tier_verified": False}
