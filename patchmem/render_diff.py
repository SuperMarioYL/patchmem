"""Render the influence-diff — before/after decision tree.

The m3 surface: ``patchmem diff`` prints which downstream ``tool_use``
decisions the patch added, removed, or altered. This module owns the rich
render of an ``InfluenceDiff`` — a structural before/after tree keyed on
``ToolUse.id``.

The render is a pure function of the diff: added = green, removed = red,
altered = yellow. It carries no causal narrative — the gate-3 honesty
guard is preserved by construction (``InfluenceDiff.changed`` is structural
and this module only displays it).
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .influence_diff import changed_input_keys
from .models import DecisionDelta, InfluenceDiff


def _preview(tu, kind: str) -> str:
    name = getattr(tu, "name", "?")
    inp = getattr(tu, "input", {}) or {}
    cmd = inp.get("command") or inp.get("path") or next(iter(inp.values()), "")
    cmd_str = str(cmd)
    if len(cmd_str) > 72:
        cmd_str = cmd_str[:71] + "…"
    return f"{name}  {cmd_str}"


def _value_str(value: object, width: int = 48) -> str:
    """One-line, width-capped rendering of an input value."""
    s = " ".join(str(value).split())
    return s if len(s) <= width else s[: width - 1] + "…"


def _altered_lines(delta: DecisionDelta) -> list[str]:
    """Lines showing exactly WHAT altered between before and after.

    The generic preview picks command/path/first-value and therefore renders
    IDENTICAL strings when the changed key is none of those — the operator
    could not see the change. These lines name the differing input keys
    (structural, via ``changed_input_keys``) and their before/after values.
    A pure tool-name change falls back to the before/after previews, which
    already display the names.
    """
    before, after = delta.before, delta.after
    if before is None or after is None:  # pragma: no cover - model validates
        return ["—"]
    if before.name != after.name:
        return [
            _preview(before, "removed"),
            f"→ {_preview(after, 'added')}",
        ]
    keys = changed_input_keys(before, after)
    if not keys:  # pragma: no cover - compute_diff only marks real differences
        return [
            _preview(before, "removed"),
            f"→ {_preview(after, 'added')}",
        ]
    lines: list[str] = []
    for k in keys:
        lines.append(f"{k}: {_value_str(before.input.get(k))}")
        lines.append(f"→ {k}: {_value_str(after.input.get(k))}")
    return lines


def render_influence_tree(diff: InfluenceDiff) -> Tree:
    """Build a rich.Tree of added / removed / altered decisions."""
    root = Tree(
        Text.assemble(
            ("influence-diff  ", "bold"),
            (f"{len(diff.changed)} changed", "bold yellow"),
        ),
        guide_style="dim",
    )

    if not diff.changed:
        root.add(Text("(no downstream decisions changed — patch was inert)", "dim italic"))
        return root

    added = root.add(Text(f"added   ({len(diff.added)})", "bold green"))
    for d in diff.added:
        added.add(Text(f"+  id={d.id[:14]}  {_preview(d.after, 'added')}", "green"))

    removed = root.add(Text(f"removed ({len(diff.removed)})", "bold red"))
    for d in diff.removed:
        removed.add(Text(f"-  id={d.id[:14]}  {_preview(d.before, 'removed')}", "red"))

    altered = root.add(Text(f"altered ({len(diff.altered)})", "bold yellow"))
    for d in diff.altered:
        branch = altered.add(Text(f"~  id={d.id[:14]}", "yellow"))
        for ln in _altered_lines(d):
            branch.add(Text(f"   {ln}", "green" if ln.startswith("→") else "red"))

    return root


def render_summary_table(diff: InfluenceDiff) -> Table:
    """Flat table view — one row per changed decision."""
    table = Table(title="patch-influence-diff", show_lines=False, border_style="yellow")
    table.add_column("kind", style="bold")
    table.add_column("tool_use id", style="magenta")
    table.add_column("name", style="cyan")
    table.add_column("before → after", overflow="fold")
    for d in diff.changed:
        kind_style = {"added": "green", "removed": "red", "altered": "yellow"}[d.kind]
        before = d.before
        after = d.after
        ba = "—"
        if d.kind == "added":
            ba = f"→ {_preview(after, 'added')}"
            name = after.name
        elif d.kind == "removed":
            ba = f"{_preview(before, 'removed')} →"
            name = before.name
        else:
            ba = "\n".join(_altered_lines(d))
            name = f"{before.name} → {after.name}"
        table.add_row(Text(d.kind, style=kind_style), d.id[:14], name, ba)
    return table


def render_diff(diff: InfluenceDiff, console: Console | None = None) -> None:
    """Print the full before/after influence surface."""
    console = console or Console()
    console.print()
    patch_preview = diff.patch.block.text.replace("\n", " ")
    if len(patch_preview) > 80:
        patch_preview = patch_preview[:79] + "…"
    console.print(
        Panel(
            f"[bold]patch[/bold]  anchor={diff.patch.anchor_uuid[:8]}  "
            f"rationale={diff.patch.rationale!r}\n"
            f"  {patch_preview}",
            title="patch applied",
            border_style="magenta",
        )
    )
    console.print(render_influence_tree(diff))
    console.print()
    console.print(render_summary_table(diff))
    console.print()
