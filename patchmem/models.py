"""Typed data model — the owned primitive: a replay-ablation decision-diff.

All models are pydantic v2 ``BaseModel`` so the wire format is machine-checkable
and round-trippable. The two load-bearing invariants for the concept-class
gate-3 honesty guard:

1. ``ToolUse.id`` is the stable decision id surfaced by the runtime
   (``toolu_...`` in Claude Code). The diff keys on it — no model attribution.
2. ``InfluenceDiff`` is computed ONLY by structural diff of two replayed
   transcripts (``control_decisions`` vs ``patched_decisions``). It NEVER
   stores or transports a model's post-hoc "this changed because of the patch"
   rationalization.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class BlockType(str, Enum):
    """Assistant message content-block kinds PatchMem recognises."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"


class TextBlock(BaseModel):
    """A scratchpad / plan / text content block.

    A Patch inserts one of these at a chosen anchor point in the transcript so
    the resumed agent reads it as new working memory.
    """

    type: Literal["text"] = "text"
    text: str = Field(..., description="Scratchpad / plan content the operator authors.")


class ToolUse(BaseModel):
    """A single agent decision — a tool_use block with a stable id.

    ``id`` is the decision address (``toolu_...``); ``name`` is the tool
    (Bash / Read / Write / TaskUpdate / ...); ``input`` is the arguments. The
    structural diff keys on ``id`` first, then ``name``/``input`` equality.
    """

    id: str = Field(..., description="Stable tool_use id, e.g. 'toolu_…'.")
    name: str = Field(..., description="Tool name: Bash | Read | Write | TaskUpdate | …")
    input: dict[str, Any] = Field(
        default_factory=dict, description="The decision's arguments."
    )

    def same_decision(self, other: ToolUse) -> bool:
        """True iff same id AND same name AND same input (structural equality)."""
        return self.id == other.id and self.name == other.name and self.input == other.input


class DecisionDelta(BaseModel):
    """A single before/after delta for one tool_use decision.

    ``kind`` ∈ {added, removed, altered}; ``before``/``after`` carry the
    control / patched decision where applicable. Pure structural record —
    no causal narrative is attached.
    """

    kind: Literal["added", "removed", "altered"]
    id: str
    before: ToolUse | None = None
    after: ToolUse | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "DecisionDelta":
        if self.kind == "added" and self.after is None:
            raise ValueError("added delta requires `after`")
        if self.kind == "removed" and self.before is None:
            raise ValueError("removed delta requires `before`")
        if self.kind == "altered" and (self.before is None or self.after is None):
            raise ValueError("altered delta requires `before` and `after`")
        return self


class Patch(BaseModel):
    """An operator-authored insertion at a chosen anchor point.

    ``anchor_uuid`` is the message uuid AFTER which to insert the new
    working-memory block (``block``). ``rationale`` is the one-line audit note
    the operator writes so the patch is traceable, not magic.
    """

    anchor_uuid: str = Field(..., description="Message uuid after which to insert.")
    block: TextBlock = Field(..., description="The new scratchpad/plan content.")
    rationale: str = Field(default="", description="Operator's one-line audit note.")


class InfluenceDiff(BaseModel):
    """The owned data structure — a replay-ablation decision-diff.

    Computed ONLY by structural diff of two replayed transcripts. The
    ``changed`` list is every tool_use the patch added, removed, or altered,
    keyed on ``ToolUse.id``. No model attribution is stored or transported —
    that is the concept-class gate-3 honesty guard.
    """

    patch: Patch
    control_decisions: list[ToolUse] = Field(
        default_factory=list, description="Decisions from the UNpatched resume."
    )
    patched_decisions: list[ToolUse] = Field(
        default_factory=list, description="Decisions from the patched resume."
    )
    changed: list[DecisionDelta] = Field(
        default_factory=list,
        description="tool_use added/removed/altered — structural diff only.",
    )

    @property
    def added(self) -> list[DecisionDelta]:
        return [d for d in self.changed if d.kind == "added"]

    @property
    def removed(self) -> list[DecisionDelta]:
        return [d for d in self.changed if d.kind == "removed"]

    @property
    def altered(self) -> list[DecisionDelta]:
        return [d for d in self.changed if d.kind == "altered"]
