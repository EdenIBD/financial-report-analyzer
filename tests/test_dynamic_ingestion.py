from unittest.mock import patch

from src.agent.nodes.check_entity import MAX_INGESTIONS_PER_QUERY, check_entity_exists
from src.ingestion.pipeline import resolve_company, resolve_ticker

FAKE_INDEX = [
    {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    {"cik_str": 1, "ticker": "APLE", "title": "Apple Hospitality REIT, Inc."},
    {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
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
        "filings": [
            {"company": f"{ticker} Corp", "fiscal_year": 2025, "filing_type": "10-K", "chunks": 120}
        ],
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


@patch("src.ingestion.pipeline._company_index", return_value=FAKE_INDEX)
def test_resolve_company_matches_despite_suffix_and_punctuation_mismatch(_mock_index):
    # BUG REAL gasit testand ingestia dinamica (2026-09-13): un LLM extrage
    # adesea "Tesla Inc" dintr-o intrebare, dar EDGAR listeaza "Tesla, Inc." —
    # nici match exact, nici prefix (virgula rupe startswith), deci compania
    # era ignorata silentios, fara nicio eroare vizibila utilizatorului.
    assert resolve_company("Tesla Inc")["ticker"] == "TSLA"
    assert resolve_company("tesla, inc.")["ticker"] == "TSLA"
    assert resolve_company("Tesla Corporation")["ticker"] == "TSLA"


@patch(
    "src.ingestion.pipeline._company_index",
    return_value=[{"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"}],
)
def test_resolve_company_matches_period_inside_name(_mock_index):
    # "Amazon.com Inc" -> stergerea (nu inlocuirea) punctuatiei ar uni
    # "amazon" si "com" intr-un singur cuvant care nu mai matcheaza
    # "AMAZON COM INC" (doua cuvinte) de pe EDGAR.
    assert resolve_company("Amazon.com Inc")["ticker"] == "AMZN"


def test_resolution_failure_blocks_unrelated_corpus():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', side_effect=RuntimeError('429')):
        state = check_entity_exists(_state('Nvidia 2023'))
    assert state['scope_blocked']
    assert state['scope_doc_ids'] == []
    assert state['ingestion_errors']


def test_existing_company_missing_year_triggers_exact_year_ingestion():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=(['NVDA'], .001, [])), \
         patch('src.agent.nodes.check_entity.available_filings', side_effect=[[], ['NVDA_2023_10K']]), \
         patch('src.agent.nodes.check_entity.ingest_company', return_value=_summary('NVDA')) as ingest:
        state = check_entity_exists(_state('Check NVDA financial report from 2023'))
    ingest.assert_called_once_with('NVDA', '10-K', 1, fiscal_year=2023)
    assert state['scope_doc_ids'] == ['NVDA_2023_10K']
    assert state['requested_years'] == [2023]
    assert not state['scope_blocked']


def test_known_and_unknown_companies_are_both_checked():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=(['AAPL','NVDA'], .001, [])), \
         patch('src.agent.nodes.check_entity.available_filings', side_effect=[['AAPL_2023'], [], ['NVDA_2023_10K']]), \
         patch('src.agent.nodes.check_entity.ingest_company', return_value=_summary('NVDA')) as ingest:
        state = check_entity_exists(_state('Compare Apple and Nvidia 2023'))
    assert ingest.call_count == 1
    assert state['scope_doc_ids'] == ['AAPL_2023','NVDA_2023_10K']


def test_complete_filing_does_not_trigger_ingestion():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=(['AAPL'], 0, [])), \
         patch('src.agent.nodes.check_entity.available_filings', return_value=['AAPL_2023']), \
         patch('src.agent.nodes.check_entity.ingest_company') as ingest:
        state = check_entity_exists(_state('Apple 2023'))
    ingest.assert_not_called()
    assert not state['scope_blocked']


def test_unresolved_registrant_abstains_without_other_sources():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=([], 0, ['Taco Bell Funding, LLC'])), \
         patch('src.agent.nodes.check_entity.ingest_company') as ingest:
        state = check_entity_exists(_state('Taco Bell Funding, LLC 2023'))
    ingest.assert_not_called()
    assert state['scope_blocked']
    assert 'SEC ticker catalog' in state['ingestion_errors'][0]


def test_failed_attempt_counts_toward_ingestion_limit():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=(['NVDA','TSLA'], 0, [])), \
         patch('src.agent.nodes.check_entity.available_filings', return_value=[]), \
         patch('src.agent.nodes.check_entity.ingest_company', side_effect=RuntimeError('SEC 429')) as ingest:
        state = check_entity_exists(_state('Compare Nvidia and Tesla 2023'))
    assert ingest.call_count == MAX_INGESTIONS_PER_QUERY
    assert state['scope_blocked']
    assert any('limit reached' in e for e in state['ingestion_errors'])


def test_general_question_keeps_general_scope():
    with patch('src.agent.nodes.check_entity.resolve_unknown_companies', return_value=([], 0, [])):
        state = check_entity_exists(_state('What are common risk factors?'))
    assert not state['scope_blocked']
    assert state['requested_tickers'] == []


def test_year_range_and_comparison_are_distinct():
    from src.agent.nodes.check_entity import requested_years
    assert requested_years('2021-2023') == [2021,2022,2023]
    assert requested_years('2021 vs 2023') == [2021,2023]
    assert requested_years('NVDA FY2023') == [2023]
