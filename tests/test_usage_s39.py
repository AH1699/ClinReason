from copy import deepcopy
import unittest

from benchmark import usage_s39 as usage


def spec(provider):
    return {"provider": provider, "model": "fixture", "input_per_million": 0.75, "output_per_million": 3.75}


def usage_fixture(provider):
    if provider == "gemini":
        return {"total_input_tokens": 7, "total_output_tokens": 20, "total_thought_tokens": 22,
                "total_tokens": 49, "total_cached_tokens": 0, "total_tool_use_tokens": 0}
    if provider == "grok":
        return {"input_tokens": 7, "output_tokens": 42, "total_tokens": 49,
                "output_tokens_details": {"reasoning_tokens": 22}, "cost_in_usd_ticks": 37756001}
    return {"prompt_tokens": 7, "completion_tokens": 42, "total_tokens": 49,
            "prompt_tokens_details": {"cached_tokens": 3}}


def raw_fixture(provider):
    return {"model": "fixture", "usage": usage_fixture(provider)}


class UsageTests(unittest.TestCase):
    def test_gemini_adds_thoughts_not_just_visible_answer(self):
        result = usage.account(raw_fixture("gemini"), spec("gemini"))
        self.assertEqual(result["usage"]["output_tokens_for_estimate"], 42)
        self.assertEqual(result["undiscounted_token_estimate_microusd"], 163)
        self.assertEqual(result["status"], "token_estimate_only")

    def test_minimax_completion_aggregate_not_double_counted(self):
        raw = raw_fixture("minimax")
        raw["usage"]["completion_tokens_details"] = {"reasoning_tokens": 22}
        result = usage.account(raw, spec("minimax"))
        self.assertEqual(result["usage"]["output_tokens_for_estimate"], 42)
        self.assertEqual(result["undiscounted_token_estimate_microusd"], 163)

    def test_grok_exact_ticks_not_rounded_or_rebuilt_from_tokens(self):
        result = usage.account(raw_fixture("grok"), spec("grok"))
        self.assertEqual(result["provider_billed_usd_ticks"], 37756001)
        self.assertIsNone(result["undiscounted_token_estimate_microusd"])
        self.assertIsNone(result["usage"]["output_tokens_for_estimate"])

    def test_zero_provider_reported_charge_is_distinct_from_missing(self):
        raw = raw_fixture("grok")
        raw["usage"]["cost_in_usd_ticks"] = 0
        self.assertEqual(usage.account(raw, spec("grok"))["status"], "provider_reported_charge")
        del raw["usage"]["cost_in_usd_ticks"]
        self.assertEqual(usage.account(raw, spec("grok"))["status"], "unknown")

    def test_reject_negative_bool_string_float_and_null_counts(self):
        for value in (-1, True, "7", 7.0, None):
            for provider, field in (("gemini", "total_input_tokens"), ("grok", "cost_in_usd_ticks"), ("minimax", "completion_tokens")):
                with self.subTest(value=value, provider=provider):
                    raw = raw_fixture(provider); raw["usage"][field] = value
                    self.assertEqual(usage.account(raw, spec(provider))["status"], "unknown")

    def test_missing_gemini_thoughts_are_not_assumed_zero(self):
        raw = raw_fixture("gemini"); del raw["usage"]["total_thought_tokens"]
        self.assertEqual(usage.account(raw, spec("gemini"))["status"], "unknown")

    def test_inconsistent_totals_remain_unknown(self):
        for provider in ("gemini", "grok", "minimax"):
            raw = raw_fixture(provider); raw["usage"]["total_tokens"] = 1
            self.assertEqual(usage.account(raw, spec(provider))["status"], "unknown")

    def test_cache_never_exceeds_input(self):
        raw = raw_fixture("gemini"); raw["usage"]["total_cached_tokens"] = 8
        self.assertEqual(usage.account(raw, spec("gemini"))["status"], "unknown")

    def test_cache_does_not_get_unverified_discount(self):
        a = raw_fixture("gemini"); b = deepcopy(a); b["usage"]["total_cached_tokens"] = 7
        self.assertEqual(usage.account(a, spec("gemini"))["undiscounted_token_estimate_microusd"],
                         usage.account(b, spec("gemini"))["undiscounted_token_estimate_microusd"])

    def test_tools_outside_protocol_rejected(self):
        for provider, field in (("gemini", "total_tool_use_tokens"), ("grok", "num_server_side_tools_used")):
            raw = raw_fixture(provider); raw["usage"][field] = 1
            self.assertEqual(usage.account(raw, spec(provider))["status"], "unknown")

    def test_wrong_model_and_missing_usage_are_not_free(self):
        for raw in (None, {}, {"model": "fixture"}, {"model": "wrong", "usage": usage_fixture("grok")}):
            result = usage.account(raw, spec("grok"))
            self.assertEqual(result["status"], "unknown")
            self.assertIsNone(result["provider_billed_usd_ticks"])

    def test_long_context_and_tier_outside_price_scope(self):
        raw = raw_fixture("gemini"); raw["service_tier"] = "priority"
        self.assertEqual(usage.account(raw, spec("gemini"))["status"], "unknown")
        del raw["service_tier"]
        raw["usage"].update(total_input_tokens=16001, total_tokens=16043)
        self.assertEqual(usage.account(raw, spec("gemini"))["status"], "unknown")

    def test_invalid_breakdown_and_reasoning_count(self):
        raw = raw_fixture("minimax"); raw["usage"]["prompt_tokens_details"] = []
        self.assertEqual(usage.account(raw, spec("minimax"))["status"], "unknown")
        raw = raw_fixture("minimax"); raw["usage"]["completion_tokens_details"] = {"reasoning_tokens": 43}
        self.assertEqual(usage.account(raw, spec("minimax"))["status"], "unknown")

    def test_summary_keeps_estimate_exact_and_unknown_separate(self):
        accounts = [usage.account(raw_fixture(p), spec(p)) for p in ("gemini", "grok", "minimax")]
        accounts.append(usage.account(None, spec("grok")))
        result = usage.summarize(accounts)
        self.assertEqual(result["provider_reported_subtotal_usd_ticks"], 37756001)
        self.assertEqual(result["token_estimate_subtotal_microusd"], 326)
        self.assertEqual(result["unknown_charge_attempts"], 1)
        self.assertIsNone(result["total_invoice_usd"])
        self.assertFalse(result["prospective_cap_proven"])
        self.assertFalse(result["all_attempts_have_provider_reported_charge"])

    def test_empty_summary_does_not_claim_invoice_complete(self):
        self.assertFalse(usage.summarize([])["all_attempts_have_provider_reported_charge"])


if __name__ == "__main__":
    unittest.main()
