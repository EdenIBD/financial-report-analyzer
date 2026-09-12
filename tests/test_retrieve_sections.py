from unittest.mock import MagicMock, patch

from src.agent.nodes.retrieve import (
    KNOWN_ENTITIES,
    PERSONA_SECTIONS,
    FALLBACK_SECTIONS,
    extract_entities,
    retrieve_multi,
)
from src.agent.state import Persona, QueryType


def test_every_persona_has_sections():
    for persona in Persona:
        assert persona in PERSONA_SECTIONS
        assert len(PERSONA_SECTIONS[persona]) > 0


def test_fallback_sections_nonempty():
    assert FALLBACK_SECTIONS


def test_extract_entities_matches_aliases():
    assert extract_entities("Cum se compara Apple si Google?") == ["AAPL", "GOOGL"]
    assert extract_entities("Ce spune Microsoft despre risc?") == ["MSFT"]
    assert extract_entities("intrebare fara nicio companie mentionata") == []


class FakeClassification:
    persona = Persona.INVESTMENT_FIRM
    query_type = QueryType.COMPARISON


@patch("src.agent.nodes.retrieve.embed_query", return_value=[0.0] * 3072)
@patch("src.agent.nodes.retrieve.qdrant_client")
def test_retrieve_multi_falls_back_to_all_companies_when_no_entity_named(mock_qdrant, mock_embed):
    # regresie: un query de comparatie fara nicio companie numita explicit
    # ("cum s-au schimbat factorii de risc din 2024 vs 2025") lasa
    # entities == [] altfel, iar bucla din retrieve_multi nu ruleaza deloc —
    # retrieved_chunks ramane gol si nu se genereaza niciun raspuns.
    empty_response = MagicMock(points=[])
    mock_qdrant.query_points.return_value = empty_response

    state = {
        "raw_query": "cum s-au schimbat factorii de risc din 2024 vs 2025",
        "classification": FakeClassification(),
        "use_fallback_sections": False,
        "retrieved_chunks": [],
    }
    retrieve_multi(state)

    queried_companies = {
        call.kwargs["query_filter"]["must"][1]["match"]["value"]
        for call in mock_qdrant.query_points.call_args_list
    }
    assert queried_companies == set(KNOWN_ENTITIES.keys())
