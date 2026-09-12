from src.storage.cost import calculate_cost_usd, PRICING_PER_MILLION_TOKENS


def test_known_model_pricing():
    cost = calculate_cost_usd("gemini-embedding-2", 1_000_000, 0)
    assert cost == PRICING_PER_MILLION_TOKENS["gemini-embedding-2"]["input"]


def test_unknown_model_costs_zero():
    assert calculate_cost_usd("nonexistent-model", 1000, 1000) == 0


def test_input_and_output_both_counted():
    cost = calculate_cost_usd("gemini-classify-model", 500_000, 500_000)
    price = PRICING_PER_MILLION_TOKENS["gemini-classify-model"]
    expected = (500_000 * price["input"] + 500_000 * price["output"]) / 1_000_000
    assert cost == expected
