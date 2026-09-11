"""m4/m5 tests — `patchmem edit` editor spawning and patch-buffer parsing.

m4 (verified on tag v0.1.0): `open_editor` passed the whole `$EDITOR` string
as one argv element, so any editor carrying a flag (``code --wait``,
``vim -f``, ``cat -u``) crashed with a raw ``FileNotFoundError`` traceback.

m5 (verified on tag v0.1.0): `parse_buffer` stripped every ``#``-prefixed
line from the operator-authored patch body, silently deleting markdown
headings from the working-memory payload — the scaffold comments live
entirely outside the ``--- patch ---`` / ``--- end ---`` markers, so the
filter only ever destroyed authored content.

These tests pin the fixed contracts for both.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from patchmem.models import Patch, TextBlock
from patchmem.patch import (
    PatchError,
    author_patch,
    open_editor,
    parse_buffer,
    prefill_buffer,
    read_patch_md,
    write_patch_md,
)
from patchmem.transcript import parse_session

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


@pytest.fixture(autouse=True)
def _no_visual_env(monkeypatch):
    # VISUAL must not shadow EDITOR in these tests.
    monkeypatch.delenv("VISUAL", raising=False)


def test_open_editor_accepts_editor_command_with_flags(monkeypatch):
    # Fail-before on v0.1.0: FileNotFoundError: 'cat -u' (the whole string
    # was one argv element). After the fix the flag is split off and `cat`
    # runs, leaving the buffer untouched for the round-trip read.
    monkeypatch.setenv("EDITOR", "cat -u")
    assert open_editor("hello\npatchmem buffer\n") == "hello\npatchmem buffer\n"


def test_open_editor_missing_editor_raises_patcherror(monkeypatch):
    monkeypatch.setenv("EDITOR", "patchmem-no-such-editor-xyz")
    with pytest.raises(PatchError, match="patchmem-no-such-editor-xyz"):
        open_editor("buffer")


def test_open_editor_plain_editor_still_works(monkeypatch):
    monkeypatch.setenv("EDITOR", "cat")
    assert open_editor("plain roundtrip") == "plain roundtrip"


def test_open_editor_nonzero_exit_raises_patcherror(monkeypatch):
    # `false` exits 1 without touching the buffer — the operator aborted.
    monkeypatch.setenv("EDITOR", "false")
    with pytest.raises(PatchError, match="exited with status"):
        open_editor("buffer")


# ---------- m5: the authored patch body is kept verbatim ----------


def _buffer(body: str, anchor: str = "msg-0002") -> str:
    return (
        "--- patch ---\n"
        f"anchor_uuid: {anchor}\n"
        "rationale: correct the plan\n"
        "---\n"
        f"{body}\n"
        "--- end ---\n"
    )


def test_parse_buffer_keeps_markdown_headings_verbatim():
    # Fail-before on v0.1.0: every '#' line was silently dropped.
    body = "# Corrected Plan\n\n1. verify JWT is HS256\n2. run make test"
    parsed = parse_buffer(_buffer(body))
    assert parsed.block_text == body


def test_parse_buffer_keeps_indented_hash_and_separator_lines():
    body = "  # indented heading\n---\nplain line\n# another heading"
    parsed = parse_buffer(_buffer(body))
    # No authored line is dropped — only whole-body edge whitespace is
    # normalised (pre-existing behaviour shared with read_patch_md).
    assert parsed.block_text == body.strip()
    assert "# indented heading" in parsed.block_text
    assert "---" in parsed.block_text
    assert "# another heading" in parsed.block_text


def test_parse_buffer_still_rejects_empty_body():
    with pytest.raises(PatchError, match="block text is empty"):
        parse_buffer(_buffer("   \n  \n"))


def test_prefill_note_no_longer_claims_hash_lines_are_ignored():
    messages = parse_session(FIXTURE)
    note = prefill_buffer(messages)
    assert "Lines starting with '#' are ignored" not in note


def test_write_read_patch_md_roundtrips_markdown_body(tmp_path):
    body = "# Corrected Plan\n\n- step one\n---\n- step two\n"
    patch = Patch(
        anchor_uuid="msg-0002",
        block=TextBlock(text=body),
        rationale="audit note",
    )
    out = write_patch_md(patch, tmp_path / "patch.md")
    assert read_patch_md(out).block.text == body.strip()


def test_author_patch_flow_preserves_markdown_through_editor(tmp_path, monkeypatch):
    # End-to-end m4+m5 repro of the verified v0.1.0 defect: a scripted editor
    # (a command WITH an argument) authors a markdown plan; on v0.1.0 this
    # crashed with FileNotFoundError before the body was even parsed.
    editor = tmp_path / "fake-editor.py"
    editor.write_text(
        "import sys\n"
        "p = sys.argv[1]\n"
        "buf = open(p, encoding='utf-8').read()\n"
        "buf = buf.replace(\n"
        "    '<your corrected plan / scratchpad content here>',\n"
        "    '# Corrected Plan\\n\\n1. verify JWT is HS256\\n2. run make test')\n"
        "open(p, 'w', encoding='utf-8').write(buf)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EDITOR", f"{sys.executable} {editor}")
    messages = parse_session(FIXTURE)
    patch = author_patch(messages)
    assert patch.block.text == (
        "# Corrected Plan\n\n1. verify JWT is HS256\n2. run make test"
    )
