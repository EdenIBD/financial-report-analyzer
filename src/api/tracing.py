from langsmith.run_helpers import get_current_run_tree

def get_current_run_id() -> str | None:
    run_tree = get_current_run_tree()
    return str(run_tree.id) if run_tree else None
