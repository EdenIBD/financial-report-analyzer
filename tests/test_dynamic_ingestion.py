from unittest.mock import patch

from src.agent.nodes.check_entity import MAX_INGESTIONS_PER_QUERY, check_entity_exists
from src.ingestion.pipeline import resolve_company, resolve_ticker

FAKE_INDEX = [
    {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    {"cik_str": 1, "ticker": "APLE", "title": "Apple Hospitality REIT, Inc."},
]


def _state(query: str) -> dict:
    return {
        "raw_query": query,
        "cost_usd": 0.0,
        "ingested_entities": [],
        "ingestion_errors": [],
        "ingestion_count": 0,
    }


def _summary(ticker: str, **overrides) -> dict:
    return {
        "ticker": ticker,
        "filings_ingested": 1,
        "chunks_indexed": 120,
        "cost_usd": 0.05,
        "errors": [],
        **overrides,
    }


@patch("src.ingestion.pipeline._company_index", return_value=FAKE_INDEX)
def test_resolve_ticker_valid(_mock_index):
    assert resolve_ticker("NVDA") == "0001045810"
    assert resolve_company("Nvidia")["ticker"] == "NVDA"  # prefix pe titlu, nu doar ticker


@patch("src.ingestion.pipeline._company_index", return_value=FAKE_INDEX)
def test_resolve_ticker_nonexistent(_mock_index):
    assert resolve_ticker("companie care nu exista pe edgar") is None


@patch("src.ingestion.pipeline._company_index", return_value=FAKE_INDEX)
def test_resolve_company_prefers_exact_company_over_longer_prefix_match(_mock_index):
    # "Apple" nu trebuie sa rezolve la "Apple Hospitality REIT": numele vine de
    # la un LLM si o rezolvare gresita declanseaza minute de ingestie inutila.
    assert resolve_company("Apple")["ticker"] == "AAPL"


@patch("src.ingestion.pipeline._company_index", return_value=FAKE_INDEX)
def test_resolve_company_rejects_too_short_name_for_prefix_match(_mock_index):
    assert resolve_company("A") is None


@patch("src.agent.nodes.check_entity.ingest_company")
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=["AAPL"])
def test_known_company_does_not_trigger_ingestion(_extract, _known, mock_ingest):
    state = check_entity_exists(_state("Ce spune Apple despre lichiditate?"))

    mock_ingest.assert_not_called()
    assert state["ingested_entities"] == []
    assert state["ingestion_errors"] == []


@patch("src.agent.nodes.check_entity.ingest_company", side_effect=lambda t, *a, **k: _summary(t))
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=["NVDA"])
def test_unknown_company_triggers_one_ingestion(_extract, _known, mock_ingest):
    state = check_entity_exists(_state("Ce spune Nvidia despre risc?"))

    assert mock_ingest.call_count == 1
    assert state["ingested_entities"] == ["NVDA"]
    assert state["ingestion_count"] == 1
    assert state["cost_usd"] == 0.05  # costul ingestiei intra in cost_usd
    assert any("Indexed NVDA" in step for step in state["trace"])


@patch("src.agent.nodes.check_entity.ingest_company", side_effect=lambda t, *a, **k: _summary(t))
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=["NVDA", "TSLA"])
def test_two_unknown_companies_respect_max_ingestions(_extract, _known, mock_ingest):
    state = check_entity_exists(_state("Compara Nvidia cu Tesla"))

    assert mock_ingest.call_count == MAX_INGESTIONS_PER_QUERY
    assert state["ingested_entities"] == ["NVDA"]
    assert any("ingestion limit reached" in e for e in state["ingestion_errors"])


@patch("src.agent.nodes.check_entity.ingest_company", side_effect=RuntimeError("EDGAR 429"))
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=["NVDA"])
def test_ingestion_failure_becomes_error_not_exception(_extract, _known, _mock_ingest):
    # un esec de ingestie nu trebuie sa opreasca query-ul: raspunsul se
    # genereaza in continuare din corpusul existent.
    state = check_entity_exists(_state("Ce spune Nvidia despre risc?"))

    assert state["ingested_entities"] == []
    assert state["ingestion_errors"] == ["NVDA: EDGAR 429"]


@patch("src.agent.nodes.check_entity.resolve_unknown_companies", return_value=(["NVDA"], 0.001))
@patch("src.agent.nodes.check_entity.ingest_company", side_effect=lambda t, *a, **k: _summary(t))
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=[])
def test_llm_tier_runs_only_when_corpus_match_finds_nothing(_extract, _known, _ingest, mock_llm):
    state = check_entity_exists(_state("What does the maker of the H100 report?"))

    mock_llm.assert_called_once()
    assert state["ingested_entities"] == ["NVDA"]


@patch("src.agent.nodes.check_entity.resolve_unknown_companies")
@patch("src.agent.nodes.check_entity.ingest_company")
@patch("src.agent.nodes.check_entity.known_tickers", return_value=["AAPL"])
@patch("src.agent.nodes.check_entity.extract_entities", return_value=["AAPL"])
def test_llm_tier_skipped_when_corpus_match_succeeds(_extract, _known, _ingest, mock_llm):
    check_entity_exists(_state("Ce spune Apple despre lichiditate?"))
    mock_llm.assert_not_called()
