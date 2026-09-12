from scripts.cost_trends import aggregate, avg, render_query_type_insight, render_table


def test_avg_of_empty_list_is_zero():
    assert avg([]) == 0.0


def test_avg_computes_mean():
    assert avg([1.0, 2.0, 3.0]) == 2.0


def test_aggregate_groups_by_persona_and_query_type():
    rows = [
        ("treasury", "factual", 0.0001, "error"),
        ("treasury", "factual", 0.0003, "valid"),
        ("legal", "risk_analysis", 0.0002, "error"),
    ]
    by_query_type, by_persona, by_status = aggregate(rows)
    assert by_query_type["factual"] == [0.0001, 0.0003]
    assert by_persona["treasury"] == [0.0001, 0.0003]
    assert by_persona["legal"] == [0.0002]
    assert by_status["error"] == [0.0001, 0.0002]
    assert by_status["valid"] == [0.0003]


def test_aggregate_skips_null_persona_or_query_type():
    rows = [(None, None, 0.0001, "error")]
    by_query_type, by_persona, by_status = aggregate(rows)
    assert by_query_type == {}
    assert by_persona == {}
    assert by_status["error"] == [0.0001]


def test_query_type_insight_computes_ratio_when_both_present():
    by_query_type = {"factual": [0.0002], "comparison": [0.0004]}
    insight = render_query_type_insight(by_query_type)
    assert "2.0x" in insight


def test_query_type_insight_reports_insufficient_data():
    by_query_type = {"factual": [0.0002]}
    insight = render_query_type_insight(by_query_type)
    assert "Insuficiente date" in insight


def test_render_table_produces_markdown_pipe_rows():
    lines = render_table(["a", "b"], [[1, 2], [3, 4]])
    assert lines[0] == "| a | b |"
    assert "| 1 | 2 |" in lines
    assert "| 3 | 4 |" in lines
