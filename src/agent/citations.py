"""Validate source identifiers; this does not establish claim faithfulness."""
import re


def inspect_citations(answer: str, available_ids: set[str]) -> dict:
    groups = re.findall(r'\[([^\]\n]+)\]', answer)
    cited = {part.strip() for group in groups for part in group.split(',') if part.strip()}
    unknown = cited - available_ids
    return {'cited_ids': sorted(cited), 'unknown_ids': sorted(unknown),
            'has_citations': bool(cited), 'all_ids_exist': bool(cited) and not unknown}
