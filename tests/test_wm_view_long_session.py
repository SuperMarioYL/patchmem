"""v0.4.0 m4 — long sessions must render without RecursionError.

``render_decision_tree`` used to recurse once per parentUuid edge, so a
linear session longer than Python's recursion limit (~1000 messages) raised
RecursionError inside ``patchmem view``. Long coding-agent sessions reach
that length. These tests pin the iterative traversal.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from patchmem.transcript import parse_session
from patchmem.wm_view import render_decision_tree

N = 1500


def _write_linear_session(path: Path, n: int = N) -> None:
    lines = []
    for i in range(n):
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "uuid": f"m{i}",
                    "parentUuid": f"m{i - 1}" if i else None,
                    "timestamp": f"2026-01-01T00:00:{i % 60:02d}",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": f"step {i}"}],
                    },
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _count_nodes(tree) -> int:
    total = 0
    stack = [tree]
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node.children)
    return total


def test_render_decision_tree_handles_deep_chain(tmp_path):
    session = tmp_path / "deep.jsonl"
    _write_linear_session(session)
    tree = render_decision_tree(parse_session(session))
    # root + one node per message
    assert _count_nodes(tree) == N + 1


def test_view_cli_handles_deep_chain(tmp_path):
    session = tmp_path / "deep.jsonl"
    _write_linear_session(session)
    env = {**os.environ, "HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "patchmem.cli", "view", str(session)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert "RecursionError" not in result.stdout + result.stderr
    assert f"{N} messages" in result.stdout
