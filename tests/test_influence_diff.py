"""m3 / concept-class gate-3 tests — the influence-diff is STRUCTURAL.

This is the honesty guard: ``compute_diff`` MUST be a mechanical
record of what the two replayed transcripts produced differently — keyed
on ``ToolUse.id`` then ``name``/``input`` equality. It MUST NOT call a
model, and ``InfluenceDiff`` MUST NOT transport a model's post-hoc "this
changed because of the patch" rationalization. If a future edit sneaks a
model attribution in, these tests fail.
"""

from __future__ import annotations

import inspect

import pytest

from patchmem.influence_diff import compute_diff, diff_from_transcripts
from patchmem.models import (
    DecisionDelta,
    InfluenceDiff,
    Patch,
    TextBlock,
    ToolUse,
)


def _patch(anchor: str = "msg-0005", rationale: str = "correct the plan") -> Patch:
    return Patch(
        anchor_uuid=anchor,
        block=TextBlock(text="plan: verify the JWT is HS256 not HS384"),
        rationale=rationale,
    )


# ---------- structural-diff cases (added / removed / altered) ----------

def test_diff_added_decision():
    """A tool_use present only in the patched arm shows up as 'added'."""
    control = [
        ToolUse(id="toolu_1", name="Bash", input={"command": "ls"}),
        ToolUse(id="toolu_2", name="Read", input={"file_path": "a.py"}),
    ]
    patched = [
        ToolUse(id="toolu_1", name="Bash", input={"command": "ls"}),
        ToolUse(id="toolu_2", name="Read", input={"file_path": "a.py"}),
        ToolUse(id="toolu_3", name="Write", input={"file_path": "b.py"}),
    ]
    d = compute_diff(_patch(), control, patched)
    assert len(d.added) == 1
    assert d.added[0].id == "toolu_3"
    assert d.added[0].after.name == "Write"
    assert not d.removed and not d.altered


def test_diff_removed_decision():
    """A tool_use present only in the control arm shows up as 'removed'."""
    control = [
        ToolUse(id="toolu_1", name="Bash", input={"command": "rm old"}),
        ToolUse(id="toolu_2", name="Read", input={"file_path": "a.py"}),
    ]
    patched = [ToolUse(id="toolu_2", name="Read", input={"file_path": "a.py"})]
    d = compute_diff(_patch(), control, patched)
    assert len(d.removed) == 1
    assert d.removed[0].id == "toolu_1"
    assert d.removed[0].before.name == "Bash"
    assert not d.added and not d.altered


def test_diff_altered_decision_same_id_different_input():
    """Same id + same name + different input → 'altered', not 'added'."""
    control = [ToolUse(id="toolu_1", name="Bash", input={"command": "make test"})]
    patched = [ToolUse(id="toolu_1", name="Bash", input={"command": "make lint"})]
    d = compute_diff(_patch(), control, patched)
    assert len(d.altered) == 1
    a = d.altered[0]
    assert a.before.input["command"] == "make test"
    assert a.after.input["command"] == "make lint"
    assert not d.added and not d.removed


def test_diff_altered_decision_same_id_different_name():
    """Same id + different name → 'altered'."""
    control = [ToolUse(id="toolu_1", name="Bash", input={"command": "x"})]
    patched = [ToolUse(id="toolu_1", name="Read", input={"file_path": "x"})]
    d = compute_diff(_patch(), control, patched)
    assert len(d.altered) == 1
    assert d.altered[0].before.name == "Bash"
    assert d.altered[0].after.name == "Read"


def test_diff_identical_arms_yield_no_changes():
    """Replay-invariant: identical arms → empty changed list."""
    arm = [ToolUse(id="toolu_1", name="Bash", input={"command": "ls"})]
    d = compute_diff(_patch(), arm, list(arm))
    assert d.changed == []
    # the control/patched decisions are still stored for the renderer.
    assert d.control_decisions == d.patched_decisions


def test_diff_input_key_order_is_invariant():
    """Dict input with reordered keys is equal — comparison is structural."""
    control = [
        ToolUse(id="toolu_1", name="Bash", input={"command": "ls", "description": "x"})
    ]
    patched = [
        ToolUse(id="toolu_1", name="Bash", input={"description": "x", "command": "ls"})
    ]
    d = compute_diff(_patch(), control, patched)
    assert d.changed == [], "reordered input keys must NOT count as altered"


def test_diff_idempotent_over_duplicate_ids():
    """Last occurrence of an id wins — replay suffixes are diffable."""
    control = [ToolUse(id="toolu_1", name="Bash", input={"command": "a"})]
    patched = [
        ToolUse(id="toolu_1", name="Bash", input={"command": "a"}),
        ToolUse(id="toolu_1", name="Bash", input={"command": "b"}),
    ]
    d = compute_diff(_patch(), control, patched)
    # the patched arm's last decision for toolu_1 differs → altered.
    assert len(d.altered) == 1
    assert d.altered[0].after.input["command"] == "b"


def test_diff_mixed_changes_categorised_correctly():
    """A combined fixture: one added, one removed, one altered, one common."""
    control = [
        ToolUse(id="t1", name="Bash", input={"command": "ls"}),
        ToolUse(id="t2", name="Read", input={"file_path": "a"}),
        ToolUse(id="t3", name="Write", input={"file_path": "x", "content": "old"}),
    ]
    patched = [
        ToolUse(id="t1", name="Bash", input={"command": "ls"}),  # common
        ToolUse(id="t2", name="Read", input={"file_path": "b"}),  # altered
        ToolUse(id="t4", name="TaskUpdate", input={"tasks": []}),  # added
        # t3 removed (no t3 in patched)
    ]
    d = compute_diff(_patch(), control, patched)
    assert {x.id for x in d.added} == {"t4"}
    assert {x.id for x in d.removed} == {"t3"}
    assert {x.id for x in d.altered} == {"t2"}
    assert len(d.changed) == 3


# ---------- concept-class gate-3 honesty guards ----------

def test_influence_diff_has_no_model_field():
    """InfluenceDiff MUST NOT carry a model-attribution field.

    If someone adds ``model_reasoning`` / ``attribution`` / ``explanation``
    to the schema, the concept-class gate-3 collapse trips here.
    """
    fields = set(InfluenceDiff.model_fields)
    forbidden = {"model_reasoning", "attribution", "explanation", "cause", "reasoning"}
    assert not (fields & forbidden), (
        f"InfluenceDiff must not carry model-attribution fields: {fields & forbidden}"
    )
    # the ONLY narrative-adjacent field is the operator's patch rationale.
    assert "rationale" in Patch.model_fields


def test_compute_diff_source_calls_no_model_or_network():
    """compute_diff's source references no LLM / requests / network libs."""
    src = inspect.getsource(compute_diff)
    banned = ("openai", "anthropic", "requests", "httpx", "llm", "chat.completions")
    hit = [b for b in banned if b in src.lower()]
    assert not hit, f"compute_diff must not reference model/network libs: {hit}"


def test_decision_delta_validates_payload_consistency():
    """DecisionDelta enforces before/after presence per kind — structural honesty."""
    with pytest.raises(Exception):
        DecisionDelta(kind="added", id="x", before=None, after=None)
    with pytest.raises(Exception):
        DecisionDelta(kind="removed", id="x", before=None, after=None)
    with pytest.raises(Exception):
        DecisionDelta(kind="altered", id="x", before=None, after=None)
    # well-formed ones construct fine.
    assert DecisionDelta(
        kind="added", id="x",
        after=ToolUse(id="x", name="Bash", input={}),
    )


def test_diff_from_transcripts_on_jsonl_lines():
    """diff_from_transcripts parses two raw JSONL transcripts then diffs.

    Proves the diff operates on the real transcript wire format, not an
    in-memory shortcut.
    """
    import json

    control_lines = [
        json.dumps(
            {"type": "assistant", "uuid": "m1", "parentUuid": None,
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "id": "toolu_1", "name": "Bash",
                  "input": {"command": "make test"}}]}}
        ),
    ]
    patched_lines = [
        json.dumps(
            {"type": "assistant", "uuid": "m1", "parentUuid": None,
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "id": "toolu_1", "name": "Bash",
                  "input": {"command": "make lint"}},
                 {"type": "tool_use", "id": "toolu_2", "name": "Write",
                  "input": {"file_path": "x"}}]}}
        ),
    ]
    d = diff_from_transcripts(_patch(), control_lines, patched_lines)
    assert {x.id for x in d.altered} == {"toolu_1"}
    assert {x.id for x in d.added} == {"toolu_2"}
