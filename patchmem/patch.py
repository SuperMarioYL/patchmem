"""Patch authoring — ``patchmem edit`` opens $EDITOR, writes patch.md.

The m1 verb: the operator inspects the live working memory (``patchmem
view``), then ``patchmem edit <session>`` opens ``$EDITOR`` pre-filled with
the current plan/scratchpad AND a header telling PatchMem where (which
anchor uuid) to insert the new block. The operator writes a corrected
plan line, saves; PatchMem parses the buffer, verifies the ``anchor_uuid``
is a real message in the transcript, and writes a machine-checkable
``patch.md`` the resume step (m2) consumes.

Patch format (the buffer the editor saves):
    --- patch ---
    anchor_uuid: <a real message uuid from the session>
    rationale: <one operator line>
    ---
    <the new scratchpad / plan content the operator authors>
    --- end ---
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import Patch, TextBlock
from .transcript import Message, message_uuids

PATCH_HEADER = "anchor_uuid"
PATCH_RATIONALE = "rationale"


class PatchError(RuntimeError):
    """Raised when an operator-authored patch is malformed or unverifiable."""


@dataclass
class ParsedPatchBuffer:
    anchor_uuid: str
    rationale: str
    block_text: str


def _default_editor() -> str:
    for var in ("EDITOR", "VISUAL"):
        ed = os.environ.get(var, "").strip()
        if ed:
            return ed
    return "vi"


def prefill_buffer(messages: list[Message], anchor_hint: str | None = None) -> str:
    """Build the editor buffer: header + current WM/plan + a patch slot.

    ``anchor_hint`` is the uuid the operator passed on the CLI (optional);
    if absent, the first assistant text block's uuid is suggested.
    """
    valid = message_uuids(messages)
    suggestion = anchor_hint or next(
        (m.uuid for m in messages if m.type == "assistant" and m.text_blocks),
        "",
    )
    wm_lines: list[str] = []
    for m in messages:
        if m.type != "assistant" or not m.text_blocks:
            continue
        wm_lines.append(f"# [existing wm] anchor={m.uuid}")
        for ln in (m.wm_text.splitlines() or [""]):
            wm_lines.append(f"#   {ln}")
        wm_lines.append("")
    wm_block = "\n".join(wm_lines) if wm_lines else "# (no existing working-memory blocks)"

    note = (
        "# patchmem edit — author a working-memory patch.\n"
        "#\n"
        "# Fill anchor_uuid (a real message uuid from `patchmem view`).\n"
        "# Add a one-line rationale (audit note).\n"
        "# Write your new scratchpad / plan content between '--- patch ---'\n"
        "# and '--- end ---'. Lines starting with '#' are ignored.\n"
        "#\n"
        f"# valid anchor count in this session: {len(valid)}\n"
        f"# suggested anchor: {suggestion}\n"
    )
    return (
        f"{note}\n"
        f"{wm_block}\n"
        f"--- patch ---\n"
        f"anchor_uuid: {suggestion}\n"
        f"rationale: <one operator line — why this patch>\n"
        f"---\n"
        f"<your corrected plan / scratchpad content here>\n"
        f"--- end ---\n"
    )


_PATCH_RE = re.compile(
    r"---\s*patch\s*---\s*\n(.*?)\n---\s*\n(.*?)\n---\s*end\s*---",
    re.DOTALL | re.IGNORECASE,
)
_KV_RE = re.compile(r"^\s*(\w+)\s*:\s*(.*?)\s*$")


def parse_buffer(buf: str) -> ParsedPatchBuffer:
    """Parse the saved editor buffer into a ParsedPatchBuffer.

    Raises ``PatchError`` if the patch/end markers are missing, or the
    anchor_uuid / block text are empty.
    """
    match = _PATCH_RE.search(buf)
    if not match:
        raise PatchError(
            "could not find '--- patch --- ... --- end ---' block in the saved buffer."
        )
    header, body = match.group(1), match.group(2)
    anchor = ""
    rationale = ""
    for line in header.splitlines():
        m = _KV_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key == PATCH_HEADER:
            anchor = val
        elif key == PATCH_RATIONALE:
            rationale = val

    block_text = "\n".join(
        ln for ln in body.splitlines() if not ln.lstrip().startswith("#")
    ).strip()

    if not anchor:
        raise PatchError("anchor_uuid is empty — set it to a real message uuid.")
    if not block_text:
        raise PatchError("patch block text is empty — write the new WM content.")
    return ParsedPatchBuffer(anchor_uuid=anchor, rationale=rationale, block_text=block_text)


def verify_anchor(anchor_uuid: str, messages: list[Message]) -> None:
    """Hard-verify the anchor uuid is a real message in the transcript."""
    if not anchor_uuid:
        raise PatchError("anchor_uuid is empty.")
    valid = message_uuids(messages)
    if anchor_uuid not in valid:
        # Offer prefix matches so the operator can recover.
        prefix_hits = [u for u in valid if u.startswith(anchor_uuid)]
        hint = (
            f" did you mean: {prefix_hits[0]}"
            if prefix_hits
            else f" valid anchors: {len(valid)} (run `patchmem view`)"
        )
        raise PatchError(f"anchor_uuid '{anchor_uuid}' is not in this session.{hint}")


def open_editor(initial: str) -> str:
    """Spawn ``$EDITOR`` on a temp file, return the saved contents."""
    editor = _default_editor()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch.md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(initial)
        path = fh.name
    try:
        subprocess.run([editor, path], check=True)
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def author_patch(messages: list[Message], anchor_hint: str | None = None) -> Patch:
    """Run the m1 edit flow: editor → parse → verify → return a Patch."""
    initial = prefill_buffer(messages, anchor_hint)
    buf = open_editor(initial)
    parsed = parse_buffer(buf)
    verify_anchor(parsed.anchor_uuid, messages)
    return Patch(
        anchor_uuid=parsed.anchor_uuid,
        block=TextBlock(text=parsed.block_text),
        rationale=parsed.rationale,
    )


def write_patch_md(patch: Patch, out_path: str | Path) -> Path:
    """Serialize a Patch to ``patch.md`` (the file m2's resume consumes)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # rationale on one line; a single '---' separates header from free-text
    # body so a body containing '---' lines stays unambiguous.
    rationale = " ".join(patch.rationale.splitlines()) or "(none)"
    content = (
        f"anchor_uuid: {patch.anchor_uuid}\n"
        f"rationale: {rationale}\n"
        f"block_type: {patch.block.type}\n"
        "---\n"
        f"{patch.block.text}\n"
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def read_patch_md(path: str | Path) -> Patch:
    """Read back a ``patch.md`` the operator (or author_patch) wrote."""
    path = Path(path)
    if not path.exists():
        raise PatchError(f"patch file not found: {path}")
    text = path.read_text(encoding="utf-8")
    # split on the FIRST line that is exactly '---' — header before, body after.
    lines = text.splitlines()
    sep_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == "---"), None
    )
    if sep_idx is None:
        raise PatchError(f"missing '---' separator in patch {path}")
    fm_lines = lines[:sep_idx]
    body = "\n".join(lines[sep_idx + 1 :]).strip()
    anchor = ""
    rationale = ""
    for line in fm_lines:
        m = _KV_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key == PATCH_HEADER:
            anchor = val
        elif key == PATCH_RATIONALE:
            rationale = val
    block_text = body.strip()
    if not anchor or not block_text:
        raise PatchError(f"patch {path} missing anchor_uuid or block text.")
    return Patch(
        anchor_uuid=anchor,
        block=TextBlock(text=block_text),
        rationale=rationale,
    )


# --- transcript-copy mutation (m1 verifies anchor; m2 actually inserts) ----

def apply_patch_to_copy(
    raw_lines: list[str], patch: Patch, messages: list[Message]
) -> list[str]:
    """Return a NEW transcript (list of raw JSONL lines) with the patch inserted.

    The inserted message is a synthetic assistant ``text`` block placed
    immediately AFTER the message whose uuid == ``patch.anchor_uuid``. The
    original transcript is never mutated — a copy is returned so the
    unpatched control arm still has the original to resume from.

    m1 verifies the anchor is real (``verify_anchor``); the structural
    insertion here is shared with m2's resume so the wire format is stable.
    """
    import json

    verify_anchor(patch.anchor_uuid, messages)

    inserted_uuid = f"patchmem-{patch.anchor_uuid[:8]}"
    new_lines: list[str] = []
    inserted = False
    for line in raw_lines:
        line = line.rstrip("\n")
        if not line:
            continue
        new_lines.append(line)
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("uuid") == patch.anchor_uuid and not inserted:
            new_lines.append(
                json.dumps(
                    {
                        "parentUuid": patch.anchor_uuid,
                        "isSidechain": False,
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": patch.block.text}
                            ],
                        },
                        "uuid": inserted_uuid,
                        "timestamp": obj.get("timestamp", ""),
                        "patchmemPatch": True,
                        "patchmemRationale": patch.rationale,
                        "cwd": obj.get("cwd", ""),
                        "sessionId": obj.get("sessionId", ""),
                        "version": obj.get("version", ""),
                        "gitBranch": obj.get("gitBranch", ""),
                    },
                    ensure_ascii=False,
                )
            )
            inserted = True
    if not inserted:
        raise PatchError(
            f"anchor_uuid {patch.anchor_uuid} not found in raw transcript lines."
        )
    return new_lines
