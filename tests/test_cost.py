from src.storage.cost import calculate_cost_usd, PRICING_PER_MILLION_TOKENS


def test_known_model_pricing():
    cost = calculate_cost_usd("gemini-embedding-001", 1_000_000, 0)
    assert cost == PRICING_PER_MILLION_TOKENS["gemini-embedding-001"]["input"]


def test_unknown_model_costs_zero():
    assert calculate_cost_usd("nonexistent-model", 1000, 1000) == 0


def test_input_and_output_both_counted():
    cost = calculate_cost_usd("gemini-3-flash-preview", 500_000, 500_000)
    price = PRICING_PER_MILLION_TOKENS["gemini-3-flash-preview"]
    expected = (500_000 * price["input"] + 500_000 * price["output"]) / 1_000_000
    assert cost == expected


def test_pricing_keys_match_real_model_constants():
    # regresie: cheile de pricing trebuie sa corespunda exact stringurilor de
    # model folosite in cod, altfel calculate_cost_usd cade tacut pe {0,0}.
    from src.agent.nodes.classify import CLASSIFY_MODEL
    from src.agent.nodes.generate import GENERATE_MODEL
    from src.ingestion.contextual import CONTEXT_MODEL

    assert CLASSIFY_MODEL in PRICING_PER_MILLION_TOKENS
    assert GENERATE_MODEL in PRICING_PER_MILLION_TOKENS
    assert CONTEXT_MODEL in PRICING_PER_MILLION_TOKENS
