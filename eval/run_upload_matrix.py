import json, sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.ingestion.detect import detect_filing_metadata, decode_filing_html
from src.ingestion.parse import parse_filing
from src.ingestion.sections import validate_sections
warnings.filterwarnings('ignore')
results=[]
for row in json.loads(Path('eval/upload-fixture-manifest.json').read_text()):
    result=dict(row)
    raw=Path(row['path']).read_bytes()
    try:
        raw.decode('utf-8'); result['strict_utf8']=True
    except UnicodeDecodeError: result['strict_utf8']=False
    stage='decode'
    try:
        html=decode_filing_html(raw)
        stage='detect'
        metadata=detect_filing_metadata(html); result['metadata']=metadata
        stage='parse'; sections=parse_filing(html,metadata['filing_type'])
        result['section_lengths']={k:len(v) for k,v in sections.items()}
        stage='validate'; validate_sections(sections)
        result['status']='passed'
    except Exception as exc:
        result.update(status='failed',stage=stage,error=f'{type(exc).__name__}: {exc}')
    results.append(result)
    print(row['id'],result['status'], result.get('stage',''), result.get('error',''),flush=True)
    Path('eval/results/upload-matrix-after.json').write_text(json.dumps(results,indent=2))
