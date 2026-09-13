"""Check citation identifiers, not whether cited passages support the claims."""
import json
from src.agent.citations import inspect_citations
from pathlib import Path


def check_citations(result):
    available = {c['chunk_id'] for c in result.get('retrieved_chunks', [])}
    return inspect_citations(result.get('answer') or '', available)


def main():
    data=json.loads(Path('eval/results/golden-set-latest.json').read_text())
    rows=[dict(question=r['question'],**check_citations(r['pipeline_result'])) for r in data['results']]
    report={'scope':'Identifier integrity only; not claim faithfulness','passed':sum(r['all_ids_exist'] for r in rows),'n':len(rows),'cases':rows}
    Path('eval/results/citation-checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(f"Citation IDs exist in retrieved context: {report['passed']}/{report['n']}")

if __name__=='__main__':
    main()
