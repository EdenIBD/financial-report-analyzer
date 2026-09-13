from unittest.mock import MagicMock, patch

from src.agent.state import Persona, QueryType
from src.storage.query_log import log_query_to_postgres


class FakeClassification:
    persona = Persona.LEGAL
    query_type = QueryType.FACTUAL


@patch("src.storage.query_log.psycopg2.connect")
def test_log_query_inserts_expected_values(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value

    log_query_to_postgres(
        raw_query="test?",
        classification=FakeClassification(),
        retrieved_chunk_ids=["c1", "c2"],
        latency_ms=123,
        final_answer="answer",
        status="valid",
        langsmith_trace_id="trace-1",
        cost_usd=0.001,
    )

    mock_cursor.execute.assert_called_once()
    args = mock_cursor.execute.call_args[0][1]
    assert args[0] == "test?"
    assert args[1] == "legal"
    assert args[2] == "factual"
    assert args[-2] == 0.001
    assert args[-1] == []
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("src.storage.query_log.psycopg2.connect")
def test_log_query_handles_missing_classification(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    log_query_to_postgres(
        raw_query="test?",
        classification=None,
        retrieved_chunk_ids=[],
        latency_ms=5,
        final_answer=None,
        status="error",
        langsmith_trace_id=None,
    )

    mock_conn.close.assert_called_once()
