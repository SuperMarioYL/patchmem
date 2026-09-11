"""m7 tests — the altered-decision render must show WHAT changed.

The v0.1.0 defect (verified on tag v0.1.0): ``_preview`` picks
``command``/``path``/first-value, so an altered decision whose changed input
key is none of those rendered IDENTICAL before/after strings — e.g. a Write
whose ``content`` changed but whose ``file_path`` did not printed
``Write  middleware/auth.py`` on both sides of the arrow, and the operator
could not see the change the diff had detected.

These tests pin the fixed contract: altered rows name the differing input
keys and render their before/after values; name-only changes and
added/removed rows keep the existing preview path.
"""

from __future__ import annotations

import io

from rich.console import Console

from patchmem.influence_diff import changed_input_keys, compute_diff
from patchmem.models import Patch, TextBlock, ToolUse
from patchmem.render_diff import render_diff


def _patch() -> Patch:
    return Patch(
        anchor_uuid="msg-0005",
        block=TextBlock(text="plan: verify the JWT is HS256 not HS384"),
        rationale="correct the plan",
    )


def _capture(diff) -> str:
    buf = io.StringIO()
    render_diff(diff, Console(file=buf, width=200))
    return buf.getvalue()


def test_altered_row_names_changed_key_and_both_values():
    # Fail-before on v0.1.0: the changed key (content) is neither command
    # nor path nor the first input key, so neither old nor new value ever
    # rendered — the row showed the identical "Write  middleware/auth.py"
    # pair on both sides of the arrow.
    control = [
        ToolUse(id="t1", name="Write",
                input={"file_path": "middleware/auth.py", "content": "old-body"})
    ]
    patched = [
        ToolUse(id="t1", name="Write",
                input={"file_path": "middleware/auth.py", "content": "NEW-patched-body"})
    ]
    out = _capture(compute_diff(_patch(), control, patched))
    assert "content" in out
    assert "old-body" in out
    assert "NEW-patched-body" in out


def test_changed_input_keys_lists_only_differing_keys():
    control = ToolUse(id="t1", name="Write",
                      input={"file_path": "a.py", "content": "x", "mode": "w"})
    patched = ToolUse(id="t1", name="Write",
                      input={"file_path": "a.py", "content": "y", "mode": "w"})
    assert changed_input_keys(control, patched) == ["content"]


def test_changed_input_keys_detects_added_and_removed_keys():
    control = ToolUse(id="t1", name="Bash", input={"command": "ls"})
    patched = ToolUse(id="t1", name="Bash", input={"command": "ls", "timeout": 5})
    assert changed_input_keys(control, patched) == ["timeout"]
    assert changed_input_keys(patched, control) == ["timeout"]


def test_altered_name_change_still_renders_both_tool_names():
    control = [ToolUse(id="t1", name="Bash", input={"command": "x"})]
    patched = [ToolUse(id="t1", name="Read", input={"file_path": "x"})]
    out = _capture(compute_diff(_patch(), control, patched))
    assert "Bash" in out
    assert "Read" in out


def test_added_and_removed_rows_keep_existing_previews():
    control = [ToolUse(id="t1", name="Bash", input={"command": "rm old"})]
    patched = [ToolUse(id="t2", name="Write", input={"file_path": "b.py"})]
    out = _capture(compute_diff(_patch(), control, patched))
    assert "rm old" in out   # removed row preview
    assert "b.py" in out     # added row preview
