from unittest.mock import MagicMock,patch
import pytest
from src.agent.citations import inspect_citations
from src.agent.nodes.generate import generate_answer
from src.agent.state import QueryClassification,Persona,QueryType

@pytest.mark.parametrize('answer,valid',[
    ('Revenue [NVDA_2023_10K_mdna_16]', True),
    ('Revenue [NVDA_2023_10K_mdna_16, NVDA_2023_10K_mdna_60]',True),
    ('Revenue [61]',False),
    ('Revenue [GOOGL_2025_Item8_33]',False),
    ('Revenue without citations',False),
    ('Revenue [NVDA_2023_10K_mdna_16] and expenses [99]',False),
])
def test_full_identifiers_required(answer,valid):
    result=inspect_citations(answer,{'NVDA_2023_10K_mdna_16','NVDA_2023_10K_mdna_60'})
    assert result['all_ids_exist'] == valid


def test_invalid_citation_abstains_and_preserves_generation_cost():
    state=dict(raw_query='NVDA FY2023',classification=QueryClassification(persona=Persona.INVESTMENT_FIRM,query_type=QueryType.FACTUAL),
        cost_usd=0,retrieved_chunks=[dict(chunk_id='NVDA_2023_10K_mdna_16',company='NVDA',fiscal_year=2023,section='mdna',text='Revenue evidence')])
    llm=MagicMock(invoke=MagicMock(return_value=MagicMock(text='Revenue [16]',usage_metadata={'input_tokens':100,'output_tokens':10})))
    with patch('src.agent.nodes.generate.generate_llm',llm):
        result=generate_answer(state)
    assert result['abstained'] and not result['sources']
    assert result['cost_usd']>0
    assert '[16]' not in result['answer']
