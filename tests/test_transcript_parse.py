"""m1 tests — Claude Code session JSONL parsing into a parentUuid-linked tree.

Proves the parser handles the smoke-verified schema: queue-operation lines
are skipped, user/assistant messages carry content blocks, tool_use blocks
surface as ``ToolUse(id, name, input)`` with stable ``id``s, and the
parentUuid tree is reconstructable. This is the m1 milestone's verifiable
contract: parse a real ``~/.claude/projects`` session shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchmem.transcript import (
    Message,
    build_tree,
    collect_decisions,
    collect_wm_text,
    find_session,
    message_uuids,
    parse_session,
)
from patchmem.models import ToolUse

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


@pytest.fixture(scope="module")
def messages() -> list[Message]:
    return parse_session(FIXTURE)


def test_fixture_exists():
    assert FIXTURE.exists(), f"missing fixture {FIXTURE}"
    # at least one non-empty line.
    lines = [ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, "fixture is empty"


def test_skips_non_conversational_lines(messages):
    # The fixture starts with a queue-operation line which must be skipped.
    types = [m.type for m in messages]
    assert "queue-operation" not in types
    # Only user / assistant survive the parser.
    assert set(types) <= {"user", "assistant"}
    assert "user" in types and "assistant" in types


def test_parent_uuid_links_form_a_chain(messages):
    # The first user message has parentUuid=None (root); every assistant
    # message's parent is a preceding message uuid present in the set.
    uuids = message_uuids(messages)
    roots = [m for m in messages if m.parent_uuid is None]
    assert len(roots) == 1, f"expected exactly one root, got {len(roots)}"
    assert roots[0].type == "user"
    for m in messages:
        if m.parent_uuid is not None:
            assert m.parent_uuid in uuids, f"dangling parent {m.parent_uuid}"


def test_build_tree_groups_by_parent(messages):
    tree = build_tree(messages)
    # root group keyed by None.
    assert None in tree
    roots = tree[None]
    assert len(roots) == 1
    # the root's child appears under its uuid.
    root = roots[0]
    assert root.uuid in tree
    assert len(tree[root.uuid]) >= 1


def test_tool_use_blocks_surface_with_stable_ids(messages):
    decisions = collect_decisions(messages)
    ids = [d.id for d in decisions]
    # Stable ids present and unique.
    assert ids, "no tool_use decisions parsed"
    assert all(i.startswith("toolu_") for i in ids), ids
    assert len(ids) == len(set(ids)), "duplicate tool_use ids"
    # Expected tool names from the fixture.
    names = {d.name for d in decisions}
    assert {"Bash", "Read", "Write", "TaskUpdate"} <= names, names


def test_tool_use_input_is_typed_dict(messages):
    decisions = collect_decisions(messages)
    bash = next(d for d in decisions if d.name == "Bash")
    assert isinstance(bash.input, dict)
    assert "command" in bash.input
    assert bash.input["command"] == "ls -la middleware/"
    # pydantic model round-trips.
    raw = bash.model_dump()
    assert ToolUse(**raw) == bash


def test_working_memory_text_collected(messages):
    wm = collect_wm_text(messages)
    assert wm, "no WM text blocks"
    # each tuple is (uuid, text); text is the concatenated assistant text.
    for uuid, text in wm:
        assert uuid
        assert text
    # the final summary text is present.
    all_text = "\n".join(t for _, t in wm)
    assert "auth middleware" in all_text.lower()


def test_message_uuids_set_supports_anchor_verification(messages):
    valid = message_uuids(messages)
    assert valid, "no uuids"
    # a real uuid from the fixture is accepted.
    assert messages[0].uuid in valid
    # an invented uuid is rejected — the anchor-verify contract.
    assert "not-a-real-uuid" not in valid


def test_parse_session_missing_file():
    with pytest.raises(Exception):
        parse_session(Path("/does/not/exist.jsonl"))


def test_find_session_resolves_direct_path():
    p = find_session(str(FIXTURE))
    assert p == FIXTURE.resolve() or p.resolve() == FIXTURE.resolve()


def test_find_session_prefix_under_projects_dir(tmp_path):
    # build a fake projects tree and look up by prefix.
    proj = tmp_path / "projects" / "repo-x"
    proj.mkdir(parents=True)
    sess = proj / "abc123def456.jsonl"
    sess.write_text(
        json.dumps(
            {
                "type": "user",
                "parentUuid": None,
                "uuid": "u1",
                "timestamp": "2026-08-17T09:00:01.000Z",
                "message": {"role": "user", "content": "hi"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    found = find_session("abc123", projects_dir=tmp_path / "projects")
    assert found.resolve() == sess.resolve()


def test_find_session_ambiguous_prefix_raises(tmp_path):
    proj = tmp_path / "projects" / "r"
    proj.mkdir(parents=True)
    (proj / "abc-1.jsonl").write_text(
        json.dumps({"type": "user", "parentUuid": None, "uuid": "u1",
                    "message": {"role": "user", "content": "a"}}) + "\n",
        encoding="utf-8",
    )
    (proj / "abc-2.jsonl").write_text(
        json.dumps({"type": "user", "parentUuid": None, "uuid": "u2",
                    "message": {"role": "user", "content": "b"}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        find_session("abc", projects_dir=tmp_path / "projects")
