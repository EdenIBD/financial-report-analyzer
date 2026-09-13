"""Replay the frozen synthetic AAPL questions; do not regenerate the benchmark.

Source-chunk Hit@8 equals single-label Recall@8 here. The originating chunk is
not an exhaustive relevance annotation: alternative correct passages count as misses.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from qdrant_client import QdrantClient
from src.retrieval.embed import embed_query


def main():
    q = QdrantClient(url=os.environ['QDRANT_URL'])
    rows = json.loads(Path('eval/retrieval_eval_AAPL_2023.json').read_text())
    for row in rows:
        results = q.query_points('financial_reports', query=embed_query(row['question']), limit=8).points
        row['retrieved_ids'] = [r.payload['chunk_id'] for r in results]
        row['hit'] = row['chunk_id'] in row['retrieved_ids']
        row['reciprocal_rank'] = 1 / (row['retrieved_ids'].index(row['chunk_id']) + 1) if row['hit'] else 0
    output = Path('eval/results/retrieval-replay.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(run_at=datetime.now(timezone.utc).isoformat(), hits=sum(r['hit'] for r in rows),
                  n=len(rows), mrr=sum(r['reciprocal_rank'] for r in rows)/len(rows), cases=rows)
    output.write_text(json.dumps(report, indent=2))
    print(f"Source-chunk Hit@8: {report['hits']}/{report['n']}; MRR: {report['mrr']:.4f}")

if __name__ == '__main__':
    main()
