"""Alembic history must stay a single line.

Two migrations written in parallel (both on top of the same parent) leave two heads, and `alembic upgrade head`
then refuses to run, which breaks a deploy. If this fails, add a merge migration: a file whose down_revision is a
tuple of the two heads and whose upgrade()/downgrade() are empty.
"""

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in VERSIONS.glob("*.py"):
        src = path.read_text()
        rev = re.search(r"^revision\s*(?::\s*str)?\s*=\s*['\"]([0-9a-f]+)['\"]", src, re.M)
        down = re.search(r"^down_revision\s*(?::[^=]+)?=\s*(.+)$", src, re.M)
        assert rev and down, f"{path.name}: could not read revision/down_revision"
        graph[rev.group(1)] = set(re.findall(r"['\"]([0-9a-f]{6,})['\"]", down.group(1)))
    return graph


def test_there_is_exactly_one_migration_head():
    graph = _graph()
    parents = {p for ps in graph.values() for p in ps}
    heads = sorted(set(graph) - parents)
    assert len(heads) == 1, f"Multiple Alembic heads {heads}: add a merge migration (see this file's docstring)."


def test_every_parent_revision_exists():
    graph = _graph()
    missing = {p for ps in graph.values() for p in ps} - set(graph)
    assert not missing, f"down_revision points at unknown revision(s): {missing}"
