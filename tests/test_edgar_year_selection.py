from unittest.mock import Mock, patch
import pytest
from src.ingestion.pipeline import download_filing


def batch(years, reports=None):
    return dict(form=['10-K']*len(years),reportDate=reports or [f'{y}-01-29' for y in years],
        filingDate=[f'{y}-02-20' for y in years],accessionNumber=[f'0001045810-{y}-00001' for y in years],
        primaryDocument=[f'nvda-{y}.htm' for y in years])


def html(year):
    return ''.join(f'<ix:nonNumeric name="dei:{k}">{v}</ix:nonNumeric>' for k,v in {
        'DocumentType':'10-K','TradingSymbol':'NVDA','DocumentFiscalYearFocus':year,
        'EntityCentralIndexKey':'1045810','EntityRegistrantName':'NVIDIA CORP'}.items())


def test_requested_year_found_in_older_submissions_shard(tmp_path):
    submissions={'filings':{'recent':batch([2026]),'files':[{'name':'CIK0001045810-submissions-001.json'}]}}
    responses=[Mock(json=lambda:submissions),Mock(json=lambda:batch([2023])),Mock(text=html(2023),content=html(2023).encode())]
    with patch('src.ingestion.pipeline.requests.get',side_effect=responses) as get, \
         patch('src.ingestion.pipeline.time.sleep'), patch('src.ingestion.pipeline.RAW_DIR',str(tmp_path)), \
         patch('src.ingestion.pipeline.DATA_DIR',str(tmp_path)):
        paths=download_filing('0001045810',ticker='NVDA',fiscal_year=2023)
    assert len(paths)==1 and '2023' in paths[0]
    assert get.call_args_list[1].args[0].endswith('submissions-001.json')
    assert '2026.htm' not in get.call_args_list[-1].args[0]


def test_report_date_is_not_fiscal_year(tmp_path):
    submissions={'filings':{'recent':batch([2024,2023],reports=['2023-12-31','2023-01-29']),'files':[]}}
    responses=[Mock(json=lambda:submissions),Mock(text=html(2024),content=html(2024).encode()),Mock(text=html(2023),content=html(2023).encode())]
    with patch('src.ingestion.pipeline.requests.get',side_effect=responses), \
         patch('src.ingestion.pipeline.time.sleep'),patch('src.ingestion.pipeline.RAW_DIR',str(tmp_path)), \
         patch('src.ingestion.pipeline.DATA_DIR',str(tmp_path)):
        paths=download_filing('0001045810',ticker='NVDA',fiscal_year=2023)
    assert len(paths)==1
    assert '2023' in paths[0]
    assert not list(tmp_path.glob('*2024*.html'))


def test_unavailable_year_does_not_download_latest(tmp_path):
    response=Mock(json=lambda:{'filings':{'recent':batch([2026]),'files':[]}})
    with patch('src.ingestion.pipeline.requests.get',return_value=response) as get, \
         patch('src.ingestion.pipeline.time.sleep'),patch('src.ingestion.pipeline.RAW_DIR',str(tmp_path)):
        with pytest.raises(ValueError,match='fiscal year 2020'):
            download_filing('0001045810',fiscal_year=2020)
    assert get.call_count==1


def test_sec_failure_propagates_without_substitution():
    response=Mock();response.raise_for_status.side_effect=RuntimeError('SEC 429')
    with patch('src.ingestion.pipeline.requests.get',return_value=response), patch('src.ingestion.pipeline.time.sleep'):
        with pytest.raises(RuntimeError,match='429'):
            download_filing('0001045810',fiscal_year=2023)
