"""Provider-reported usage, not prospective spending authorization.

Keep integer xAI billing ticks exact. Other prices are undiscounted token
estimates, never an invoice or an upper bound on an unsent request.
"""

from decimal import Decimal, ROUND_CEILING


class UsageError(ValueError):
    pass


def counter(obj, name, required=True):
    value = obj.get(name)
    if value is None and not required and name not in obj:
        return None
    if type(value) is not int or value < 0:
        raise UsageError("Missing or invalid usage counter")
    return value


def detail(usage, name, field):
    if name not in usage:
        return None
    value = usage[name]
    if not isinstance(value, dict):
        raise UsageError("Invalid usage breakdown")
    return counter(value, field, False)


def normalize(raw, provider):
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if not isinstance(usage, dict):
        raise UsageError("Missing provider usage")
    thought = cached = billed_ticks = None
    if provider == "gemini":
        inputs = counter(usage, "total_input_tokens")
        outputs = counter(usage, "total_output_tokens")
        thought = counter(usage, "total_thought_tokens")
        total = counter(usage, "total_tokens")
        cached = counter(usage, "total_cached_tokens", False)
        tools = counter(usage, "total_tool_use_tokens", False)
        if tools not in (None, 0) or usage.get("grounding_tool_count") not in (None, []):
            raise UsageError("Tool usage outside text-only protocol")
        output_basis = outputs + thought
        if total != inputs + output_basis:
            raise UsageError("Unreconciled Gemini token total")
        basis = "answer_plus_thought_tokens"
    elif provider in {"grok", "minimax"}:
        first, last = ("input_tokens", "output_tokens") if provider == "grok" else ("prompt_tokens", "completion_tokens")
        inputs, outputs, total = (counter(usage, n) for n in (first, last, "total_tokens"))
        cached = detail(usage, first + "_details", "cached_tokens")
        thought = detail(usage, last + "_details", "reasoning_tokens")
        if provider == "grok":
            # Do not infer output/reasoning inclusion from the OpenAI-shaped keys.
            # Cost ticks independently cover the whole request, including reasoning.
            billed_ticks = counter(usage, "cost_in_usd_ticks")
            tools = counter(usage, "num_server_side_tools_used", False)
            if tools not in (None, 0) or total < inputs + outputs:
                raise UsageError("Unsupported Grok usage")
            output_basis, basis = None, "provider_billed_ticks_no_token_cost_inference"
        else:
            if total != inputs + outputs or (thought is not None and thought > outputs):
                raise UsageError("Unreconciled MiniMax token total")
            output_basis, basis = outputs, "reported_completion_tokens"
    else:
        raise UsageError("Unsupported provider")
    if cached is not None and cached > inputs:
        raise UsageError("Cached count exceeds input")
    return {"input_tokens": inputs, "reported_output_tokens": outputs, "thought_tokens": thought,
        "total_tokens": total, "cached_input_tokens": cached, "output_tokens_for_estimate": output_basis,
        "provider_billed_usd_ticks": billed_ticks, "basis": basis}


def account(raw, spec):
    """Unknown costs stay unknown, including HTTP failures and mismatched models."""
    result = {"status": "unknown", "provider_billed_usd_ticks": None,
              "undiscounted_token_estimate_microusd": None, "usage": None,
              "prospective_cap_proven": False}
    if not isinstance(raw, dict) or raw.get("model") != spec["model"]:
        result["reason"] = "model_identity_unverified"
        return result
    try:
        usage = normalize(raw, spec["provider"])
    except UsageError:
        result["reason"] = "missing_invalid_or_unsupported_usage"
        return result
    result["usage"] = usage
    if usage["provider_billed_usd_ticks"] is not None:
        result.update(status="provider_reported_charge", provider_billed_usd_ticks=usage["provider_billed_usd_ticks"])
        return result
    # The S38 short-context roster price is not valid for arbitrary long requests.
    if usage["input_tokens"] > 16000 or raw.get("service_tier") not in (None, "standard"):
        result["reason"] = "outside_verified_short_context_standard_price_scope"
        return result
    rates = [Decimal(str(spec[n])) for n in ("input_per_million", "output_per_million")]
    if any(not r.is_finite() or r < 0 for r in rates):
        raise ValueError("Invalid experiment price")
    value = usage["input_tokens"]*rates[0] + usage["output_tokens_for_estimate"]*rates[1]
    result.update(status="token_estimate_only",
                  undiscounted_token_estimate_microusd=int(value.to_integral_value(rounding=ROUND_CEILING)))
    return result


def summarize(accounts):
    """Separate exact provider-reported subtotals from estimates and unknowns."""
    return {"attempts": len(accounts),
        "provider_reported_charge_count": sum(a["status"] == "provider_reported_charge" for a in accounts),
        "provider_reported_subtotal_usd_ticks": sum(a["provider_billed_usd_ticks"] or 0 for a in accounts),
        "token_estimate_count": sum(a["status"] == "token_estimate_only" for a in accounts),
        "token_estimate_subtotal_microusd": sum(a["undiscounted_token_estimate_microusd"] or 0 for a in accounts),
        "unknown_charge_attempts": sum(a["status"] == "unknown" for a in accounts),
        "all_attempts_have_provider_reported_charge": bool(accounts) and all(a["status"] == "provider_reported_charge" for a in accounts),
        "total_invoice_usd": None, "prospective_cap_proven": False}
