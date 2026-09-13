from unittest.mock import MagicMock, patch

from src.agent.nodes.retrieve import (
    PERSONA_SECTIONS,
    FALLBACK_SECTIONS,
    extract_entities,
    retrieve_multi,
)
from src.agent.state import Persona, QueryType

CORPUS = [("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corporation"), ("GOOGL", "Alphabet Inc.")]


def test_every_persona_has_sections():
    for persona in Persona:
        assert persona in PERSONA_SECTIONS
        assert len(PERSONA_SECTIONS[persona]) > 0


def test_fallback_sections_nonempty():
    assert FALLBACK_SECTIONS


@patch("src.agent.nodes.retrieve.known_companies", return_value=CORPUS)
def test_extract_entities_matches_corpus(_mock_corpus):
    assert extract_entities("Cum se compara Apple si Google?") == ["AAPL", "GOOGL"]
    assert extract_entities("Ce spune Microsoft despre risc?") == ["MSFT"]
    assert extract_entities("intrebare fara nicio companie mentionata") == []


@patch("src.agent.nodes.retrieve.known_companies", return_value=CORPUS)
def test_extract_entities_matches_brand_name_not_in_registrant_name(_mock_corpus):
    # "Alphabet Inc." nu contine "Google": fara alias, intrebarile despre Google
    # ar cauta in tot corpusul in loc de GOOGL.
    assert extract_entities("What does Google say about antitrust?") == ["GOOGL"]


@patch("src.agent.nodes.retrieve.known_companies", return_value=CORPUS + [("F", "Ford Motor Co")])
def test_extract_entities_does_not_match_single_letter_ticker_inside_words(_mock_corpus):
    # cu corpus deschis (upload + ingestie dinamica) pot aparea tickere de o
    # litera; un match pe substring le-ar gasi in aproape orice intrebare.
    assert extract_entities("What are the risk factors for Apple?") == ["AAPL"]


class FakeClassification:
    persona = Persona.INVESTMENT_FIRM
    query_type = QueryType.COMPARISON


@patch("src.agent.nodes.retrieve.known_tickers", return_value=["AAPL", "GOOGL", "MSFT"])
@patch("src.agent.nodes.retrieve.known_companies", return_value=CORPUS)
@patch("src.agent.nodes.retrieve.embed_query", return_value=[0.0] * 3072)
@patch("src.agent.nodes.retrieve.qdrant_client")
def test_retrieve_multi_falls_back_to_all_companies_when_no_entity_named(
    mock_qdrant, _mock_embed, _mock_corpus, _mock_tickers
):
    # regresie: un query de comparatie fara nicio companie numita explicit
    # ("cum s-au schimbat factorii de risc din 2024 vs 2025") lasa
    # entities == [] altfel, iar bucla din retrieve_multi nu ruleaza deloc —
    # retrieved_chunks ramane gol si nu se genereaza niciun raspuns.
    mock_qdrant.query_points.return_value = MagicMock(points=[])

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
    assert queried_companies == {"AAPL", "GOOGL", "MSFT"}
