"""Transcript parsing — Claude Code session JSONL → parentUuid-linked tree.

The Claude Code session transcript lives at
``~/.claude/projects/*/<session>.jsonl`` — one JSON object per line. The
schema (smoke-verified against this machine's real sessions):

    {
      "type": "user" | "assistant" | "system" | "attachment" | ...,
      "uuid": "<message-uuid>",
      "parentUuid": "<parent-uuid>" | null,
      "timestamp": "ISO-8601",
      "sessionId": "<session-id>",
      "cwd": "<repo-path>",
      "gitBranch": "<branch>",
      "version": "<runtime-version>",
      "message": {                          # for user / assistant
        "role": "user" | "assistant",
        "content": str | [block, ...]       # blocks: {type:text|tool_use|tool_result, ...}
      }
    }

A ``tool_use`` block looks like::

    {"type": "tool_use", "id": "toolu_…", "name": "Bash", "input": {...}}

PatchMem cares about three things: the parentUuid-linked tree (decision
order), the tool_use blocks (decisions), and the text blocks the agent wrote
(the working-memory / plan / scratchpad surface the operator patches).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .models import TextBlock, ToolUse

# Default location of Claude Code session transcripts on this machine.
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"


class TranscriptError(RuntimeError):
    """Raised when a transcript cannot be parsed or a session cannot be found."""


@dataclass
class Message:
    """A single parsed transcript line — typed, parentUuid-linked."""

    uuid: str
    parent_uuid: str | None
    type: str
    timestamp: str
    role: str | None
    text_blocks: list[TextBlock] = field(default_factory=list)
    tool_uses: list[ToolUse] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def decisions(self) -> list[ToolUse]:
        """Alias for tool_uses — a decision IS a tool_use."""
        return self.tool_uses

    @property
    def wm_text(self) -> str:
        """Concatenated assistant text blocks — the WM/plan surface."""
        return "\n".join(b.text for b in self.text_blocks).strip()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise TranscriptError(
                    f"{path}:{lineno}: invalid JSON ({exc.msg})"
                ) from exc


def _content_blocks(message: dict[str, Any]) -> tuple[list[TextBlock], list[ToolUse]]:
    """Split an assistant/user message's content into text + tool_use blocks."""
    texts: list[TextBlock] = []
    tools: list[ToolUse] = []
    content = message.get("content")
    if isinstance(content, str):
        # user role often carries a plain string (the prompt).
        texts.append(TextBlock(text=content))
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                texts.append(TextBlock(text=block.get("text", "")))
            elif btype == "tool_use":
                tools.append(
                    ToolUse(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        input=block.get("input", {}) or {},
                    )
                )
    return texts, tools


def parse_session(path: str | Path) -> list[Message]:
    """Parse a Claude Code session JSONL into a parentUuid-linked list.

    Non-conversational lines (queue-operation / mode / custom-title /
    last-prompt / attachment) are skipped — they are runtime bookkeeping,
    not decisions or working memory.
    """
    path = Path(path)
    if not path.exists():
        raise TranscriptError(f"session file not found: {path}")
    messages: list[Message] = []
    for obj in _iter_jsonl(path):
        mtype = obj.get("type")
        # Only user / assistant carry the message + content blocks we diff.
        if mtype not in ("user", "assistant"):
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        texts, tools = _content_blocks(msg)
        messages.append(
            Message(
                uuid=obj.get("uuid", ""),
                parent_uuid=obj.get("parentUuid"),
                type=mtype,
                timestamp=obj.get("timestamp", ""),
                role=msg.get("role"),
                text_blocks=texts,
                tool_uses=tools,
                raw=obj,
            )
        )
    return messages


def build_tree(messages: list[Message]) -> dict[str | None, list[Message]]:
    """Group messages by parentUuid — the decision-tree skeleton.

    The root's parent is ``None``. Returns ``{parent_uuid: [child, ...]}``.
    """
    tree: dict[str | None, list[Message]] = {}
    for m in messages:
        tree.setdefault(m.parent_uuid, []).append(m)
    for children in tree.values():
        children.sort(key=lambda x: x.timestamp)
    return tree


def collect_decisions(messages: list[Message]) -> list[ToolUse]:
    """Flatten every tool_use decision in transcript order."""
    out: list[ToolUse] = []
    for m in messages:
        if m.type == "assistant":
            out.extend(m.tool_uses)
    return out


def collect_wm_text(messages: list[Message]) -> list[tuple[str, str]]:
    """Return ``[(uuid, text), ...]`` of every assistant text block.

    These are the working-memory / plan / scratchpad surfaces the operator
    may patch. Order = transcript order.
    """
    out: list[tuple[str, str]] = []
    for m in messages:
        if m.type == "assistant" and m.text_blocks:
            out.append((m.uuid, m.wm_text))
    return out


def find_session(session_ref: str, projects_dir: Path | None = None) -> Path:
    """Resolve a session id (or prefix) to a JSONL path.

    ``session_ref`` may be a full path, a bare session id, or a unique prefix
    of one. Searches ``projects_dir`` (default ``~/.claude/projects/*``).
    """
    projects_dir = projects_dir or DEFAULT_PROJECTS_DIR
    ref = os.path.expanduser(str(session_ref))

    # 1. Direct path.
    p = Path(ref)
    if p.exists() and p.is_file() and p.suffix == ".jsonl":
        return p

    # 2. Filename = <session-id>.jsonl anywhere under projects_dir.
    if not projects_dir.exists():
        raise TranscriptError(
            f"projects dir not found: {projects_dir} (is Claude Code installed?)"
        )

    candidates: list[Path] = []
    # bare id or prefix — match against file stems.
    stem = p.stem if p.suffix == ".jsonl" else ref
    for root, _dirs, files in os.walk(projects_dir):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            file_stem = name[: -len(".jsonl")]
            if file_stem == stem or file_stem.startswith(stem) or stem in file_stem:
                candidates.append(Path(root) / name)

    if not candidates:
        raise TranscriptError(
            f"no session matching '{session_ref}' under {projects_dir}"
        )
    if len(candidates) > 1:
        # Prefer exact-id matches; if still ambiguous, raise so the operator disambiguates.
        exact = [c for c in candidates if c.stem == stem]
        if len(exact) == 1:
            return exact[0]
        raise TranscriptError(
            f"ambiguous session ref '{session_ref}': "
            f"{len(candidates)} matches — use a longer prefix:\n  "
            + "\n  ".join(str(c) for c in candidates[:8])
        )
    return candidates[0]


def message_uuids(messages: list[Message]) -> set[str]:
    """Set of all valid anchor uuids (every message's own uuid)."""
    return {m.uuid for m in messages if m.uuid}
