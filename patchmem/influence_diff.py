"""Influence-diff — the owned primitive: a replay-ablation decision-diff.

The core algorithm. It diffs two replayed transcripts (the unpatched
``control`` arm and the ``patched`` arm) by their ``tool_use`` blocks,
keyed on ``ToolUse.id`` first, then ``name`` / ``input`` equality. The
result is a structural record — ``added`` / ``removed`` / ``altered`` —
NEVER a model's post-hoc "this changed because of the patch"
rationalization. That is the concept-class gate-3 honesty guard.

This module is implemented and unit-tested in v0.1 (it is the owned
primitive from §2); the CLI ``patchmem diff`` wires it to the m2 replay
output. ``compute_diff`` accepts two ``list[ToolUse]`` directly so the
test on a fixture pair of transcripts proves the diff is structural.
"""

from __future__ import annotations

from collections import OrderedDict

from .models import DecisionDelta, InfluenceDiff, Patch, ToolUse


def _index(decisions: list[ToolUse]) -> "OrderedDict[str, ToolUse]":
    """Index decisions by id — last occurrence wins (idempotent over suffix)."""
    out: "OrderedDict[str, ToolUse]" = OrderedDict()
    for d in decisions:
        out[d.id] = d
    return out


def _normalise_input(value: object) -> object:
    """Make ``input`` dict comparison order-stable (sorted keys)."""
    if isinstance(value, dict):
        return {k: _normalise_input(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_normalise_input(v) for v in value]
    return value


def _inputs_equal(a: dict, b: dict) -> bool:
    return _normalise_input(a) == _normalise_input(b)


def changed_input_keys(before: ToolUse, after: ToolUse) -> list[str]:
    """Input keys whose normalised values differ between two decisions.

    Companion to the altered-detection comparison in ``compute_diff``: the
    renderer uses it to show exactly WHICH arguments changed. Key order is
    before-order then new-in-after order — stable for rendering.
    """
    keys = list(dict.fromkeys([*before.input, *after.input]))
    return [
        k
        for k in keys
        if _normalise_input(before.input.get(k)) != _normalise_input(after.input.get(k))
    ]


def compute_diff(
    patch: Patch,
    control_decisions: list[ToolUse],
    patched_decisions: list[ToolUse],
) -> InfluenceDiff:
    """Structurally diff two replayed decision lists.

    * ``added``   — id present in patched, absent in control.
    * ``removed`` — id present in control, absent in patched.
    * ``altered`` — id present in both, but name or input differs.

    The diff is computed by id-keyed set operations + per-id equality — no
    model call, no ordering heuristic beyond the id index. This is the
    honesty guard: the ``changed`` list is a mechanical record of what
    replay produced differently, full stop.
    """
    control = _index(control_decisions)
    patched = _index(patched_decisions)
    control_ids = set(control)
    patched_ids = set(patched)

    deltas: list[DecisionDelta] = []

    # altered + removed: iterate control order for stable output.
    for did, before in control.items():
        if did in patched:
            after = patched[did]
            if before.name != after.name or not _inputs_equal(before.input, after.input):
                deltas.append(
                    DecisionDelta(kind="altered", id=did, before=before, after=after)
                )
        else:
            deltas.append(DecisionDelta(kind="removed", id=did, before=before))

    # added: ids only in patched, in patched order.
    for did, after in patched.items():
        if did not in control_ids:
            deltas.append(DecisionDelta(kind="added", id=did, after=after))

    return InfluenceDiff(
        patch=patch,
        control_decisions=list(control.values()),
        patched_decisions=list(patched.values()),
        changed=deltas,
    )


def diff_from_transcripts(
    patch: Patch,
    control_lines: list[str],
    patched_lines: list[str],
) -> InfluenceDiff:
    """Convenience: parse two raw JSONL transcripts then diff.

    Lets the CLI ``patchmem diff`` and the unit test operate on fixture
    files without re-parsing by hand.
    """
    from .transcript import parse_session, collect_decisions

    # ``parse_session`` takes a path; here we accept raw lines, so write a
    # tiny shim that reuses the same per-line parser.
    import json
    from .transcript import Message, _content_blocks  # type: ignore[attr-defined]

    def _lines_to_decisions(lines: list[str]) -> list[ToolUse]:
        out: list[ToolUse] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            _, tools = _content_blocks(msg)
            out.extend(tools)
        return out

    return compute_diff(
        patch,
        _lines_to_decisions(control_lines),
        _lines_to_decisions(patched_lines),
    )
