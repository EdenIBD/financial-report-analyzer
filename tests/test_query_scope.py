from unittest.mock import MagicMock, patch
import pytest
from src.agent.nodes.retrieve import retrieve_single, retrieve_multi
from src.agent.nodes.generate import generate_answer
from src.agent.graph import graph, route_after_classify
from src.agent.state import QueryClassification, Persona, QueryType


def scoped_state():
    return dict(raw_query='NVDA 2023', requested_tickers=['NVDA'], requested_years=[2023],
        scope_doc_ids=['NVDA_2023_10K'], scope_blocked=False, use_fallback_sections=False,
        classification=QueryClassification(persona=Persona.INVESTMENT_FIRM,query_type=QueryType.FACTUAL),
        retrieved_chunks=[], retry_count=0, cost_usd=0, sources=[])


@pytest.mark.parametrize('retrieve',[retrieve_single,retrieve_multi])
@pytest.mark.parametrize('fallback',[False,True])
def test_company_year_and_document_filters_survive_both_routes_and_retry(retrieve,fallback):
    state=scoped_state();state['use_fallback_sections']=fallback
    with patch('src.agent.nodes.retrieve.embed_query',return_value=[0.0]), \
         patch('src.agent.nodes.retrieve.qdrant_client') as q:
        q.query_points.return_value=MagicMock(points=[])
        retrieve(state)
    assert q.query_points.call_count == 2
    for call in q.query_points.call_args_list:
        conditions=call.kwargs['query_filter']['must']
        assert {'key':'company','match':{'any':['NVDA']}} in conditions
        assert {'key':'fiscal_year','match':{'any':[2023]}} in conditions
        assert {'key':'doc_id','match':{'any':['NVDA_2023_10K']}} in conditions


def test_blocked_scope_short_circuits_graph_and_generation():
    state=scoped_state();state['scope_blocked']=True
    assert route_after_classify(state)=='generate_answer'
    with patch('src.agent.nodes.generate.generate_llm') as llm:
        answer=generate_answer(state)
    llm.invoke.assert_not_called()
    assert answer['sources']==[] and answer['abstained']


def test_empty_context_abstains_without_llm():
    with patch('src.agent.nodes.generate.generate_llm') as llm:
        result=generate_answer(scoped_state())
    assert result['abstained'] and result['sources']==[]
    llm.invoke.assert_not_called()


def test_graph_stream_preserves_scope_through_verification_retry():
    # Real compiled graph; only external services are mocked.
    state=scoped_state();state.update(ingestion_count=0,ingested_entities=[],ingestion_errors=[],trace=[])
    raw=MagicMock(usage_metadata={},text='Supported response [NVDA_2023_10K_mdna_0]')
    classification={'parsed':state['classification'],'raw':raw}
    entity_result={'parsed':MagicMock(companies=['NVDA']),'raw':raw}
    point=MagicMock(id='point',score=.1,payload=dict(chunk_id='NVDA_2023_10K_mdna_0',
        doc_id='NVDA_2023_10K',company='NVDA',fiscal_year=2023,section='mdna',text='NVIDIA evidence'))
    with patch('src.agent.nodes.classify.classify_llm', MagicMock(invoke=MagicMock(return_value=classification))), \
         patch('src.agent.nodes.check_entity._entity_llm', MagicMock(invoke=MagicMock(return_value=entity_result))), \
         patch('src.agent.nodes.check_entity.extract_entities',return_value=['NVDA']), \
         patch('src.agent.nodes.check_entity.available_filings',return_value=['NVDA_2023_10K']), \
         patch('src.agent.nodes.retrieve.embed_query',return_value=[0.0]), \
         patch('src.agent.nodes.retrieve.qdrant_client') as q, \
         patch('src.retrieval.rerank.get_ranking_client',return_value=MagicMock(rank=MagicMock(return_value=MagicMock(records=[MagicMock(id=point.payload['chunk_id'],score=.1)])))), \
         patch('src.agent.nodes.generate.generate_llm', MagicMock(invoke=MagicMock(return_value=raw))):
        q.query_points.return_value=MagicMock(points=[point])
        updates=list(graph.stream(state,stream_mode='values'))
    assert updates[-1]['retry_count']==2
    assert len(updates)<20
    assert updates[-1]['sources']==['NVDA_2023_10K_mdna_0']
    for call in q.query_points.call_args_list:
        assert {'key':'fiscal_year','match':{'any':[2023]}} in call.kwargs['query_filter']['must']
