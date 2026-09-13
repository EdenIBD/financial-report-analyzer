"""Live pipeline checks for observed company/year substitution failures.

These deterministic checks measure source scope, not financial correctness.
Raw answers, retrieved evidence, trace and costs are persisted for review.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from src.api.main import handle_query

CASES = [
    ('nvidia_2023', 'Check NVDA financial report from 2023 and summarize it', ['NVDA'], [2023], False),
    ('nvidia_2023_ro', 'Rezumă raportul financiar Nvidia din 2023', ['NVDA'], [2023], False),
    ('taco_bell_unresolved', 'Check Taco Bell Funding, LLC financial report from 2023 and summarize it', [], [2023], True),
    ('mixed_companies', 'Compare Apple and Nvidia financial performance in 2023', ['AAPL','NVDA'], [2023], False),
    ('missing_year', 'Summarize Nvidia fiscal year 2099 annual report', ['NVDA'], [2099], True),
]

def check_scope(result, companies, years, should_abstain):
    chunks = result.get('retrieved_chunks', [])
    if should_abstain:
        return result['status'] == 'abstained' and not chunks and not result['sources']
    return (result['status'] == 'valid' and bool(chunks)
        and {c['company'] for c in chunks} == set(companies)
        and all(c['fiscal_year'] in years for c in chunks))


def main():
    path=Path('eval/results/scope-regressions.json');path.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,question,companies,years,abstain in CASES:
        result=handle_query(question)
        passed=check_scope(result,companies,years,abstain)
        rows.append(dict(case=name,question=question,expected_companies=companies,expected_years=years,
                         expected_abstention=abstain,passed=passed,result=result))
        path.write_text(json.dumps(dict(run_at=datetime.now(timezone.utc).isoformat(),cases=rows),indent=2,ensure_ascii=False))
        print(f'{name}: {"PASS" if passed else "FAIL"} status={result["status"]} chunks={len(result["retrieved_chunks"])} elapsed={result["latency_ms"]}ms',flush=True)
    if not all(r['passed'] for r in rows):
        raise SystemExit(1)

if __name__=='__main__':
    main()
