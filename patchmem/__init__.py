"""patchmem — patch-as-commit-to-working-memory primitive for coding-agent runs.

PatchMem pauses a coding-agent run mid-flight, lets the operator write a patch
into the live working memory / scratchpad / plan (not just cut turns), resumes
the run for a patched and an unpatched control arm, and surfaces a
machine-checkable patch-influence-diff of every downstream tool_use decision
that changed because of the patch. v0.1 targets Claude Code session
transcripts under ``~/.claude/projects/``.

Public surface (stable for v0.1.x):
    from patchmem.models import ToolUse, TextBlock, Patch, InfluenceDiff, DecisionDelta
    from patchmem.transcript import parse_session, find_session
    from patchmem.cli import app
"""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["__version__"]
