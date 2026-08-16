"""Working-memory + decision-tree viewer — the rich TUI for ``patchmem view``.

Renders, for a parsed session:
    * the parentUuid-linked decision tree (assistant tool_use blocks keyed by id),
    * the current working-memory / plan / scratchpad blocks (assistant text),
    * the list of valid anchor points the operator may patch at.

No mutation happens here — view is read-only; ``patchmem edit`` does the write.
"""

from __future__ import annotations

from typing import Iterable

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .transcript import Message, build_tree, collect_wm_text


def _short(text: str, width: int = 64) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _decision_summary(msg: Message) -> Text:
    if msg.tool_uses:
        names = ", ".join(sorted({t.name for t in msg.tool_uses}))
        ids = ", ".join(t.id[:14] for t in msg.tool_uses)
        return Text(
            f"tool_use [{names}]  id={ids}",
            style="bold cyan",
        )
    return Text("(text only)", style="dim")


def render_decision_tree(messages: list[Message], console: Console | None = None) -> Tree:
    """Build a rich.Tree of the parentUuid-linked decision sequence.

    Roots are messages with ``parent_uuid is None``; each node shows the
    message type, uuid prefix, timestamp, and decision summary.
    """
    console = console or Console()
    tree_map = build_tree(messages)
    uuid_to_msg = {m.uuid: m for m in messages}

    def add_children(node, parent_uuid: str | None) -> None:
        for child in tree_map.get(parent_uuid, []):
            label = Text.assemble(
                (f"{child.type:<9} ", "bold"),
                (f"{child.uuid[:8]}  ", "dim"),
                (child.timestamp[:19], "green"),
                "  ",
                _decision_summary(child),
            )
            branch = node.add(label)
            add_children(branch, child.uuid)

    root = Tree("session", guide_style="dim cyan")
    # Attach any orphan (parent not in set) under root too.
    add_children(root, None)
    # Orphans whose parent is missing — surface them so the operator sees gaps.
    known = set(uuid_to_msg) | {None}
    for parent_uuid, kids in tree_map.items():
        if parent_uuid in known:
            continue
        orphan_branch = root.add(Text(f"(broken parent {str(parent_uuid)[:8]})", "yellow"))
        for child in kids:
            orphan_branch.add(
                Text.assemble(
                    (f"{child.type:<9} ", "bold"),
                    (child.uuid[:8], "dim"),
                    "  ",
                    _decision_summary(child),
                )
            )
    return root


def render_wm_blocks(wm: Iterable[tuple[str, str]], console: Console | None = None) -> Panel:
    """Render the working-memory / plan / scratchpad blocks as a panel."""
    console = console or Console()
    lines: list[Text] = []
    for i, (uuid, text) in enumerate(wm, 1):
        block = Text.assemble(
            (f"[{i}] anchor={uuid[:8]}  ", "bold magenta"),
        )
        for ln in text.splitlines() or [""]:
            block.append(Text(f"    {ln}", "white"))
        lines.append(block)
        lines.append(Text(""))
    if not lines:
        lines = [Text("(no working-memory / plan blocks in this session)", "dim italic")]
    return Panel(Group(*lines), title="working memory / plan", border_style="magenta")


def render_anchors(messages: list[Message], console: Console | None = None) -> Table:
    """Table of valid anchor uuids for ``patchmem edit``."""
    console = console or Console()
    table = Table(title="valid patch anchors", show_lines=False, border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("anchor uuid", style="bold magenta")
    table.add_column("type", style="cyan")
    table.add_column("preview", overflow="fold")
    for i, m in enumerate(messages, 1):
        preview = m.wm_text or (m.tool_uses[0].name if m.tool_uses else "")
        table.add_row(str(i), m.uuid, m.type, _short(preview))
    return table


def view_session(messages: list[Message], console: Console | None = None) -> None:
    """Top-level view: decision tree + WM blocks + anchor table."""
    console = console or Console()
    console.print()
    console.print(
        Panel(
            f"[bold]session[/bold]  {len(messages)} messages  "
            f"{sum(len(m.tool_uses) for m in messages)} tool_use decisions",
            border_style="blue",
        )
    )
    console.print(render_decision_tree(messages, console))
    console.print()
    wm = collect_wm_text(messages)
    console.print(render_wm_blocks(wm, console))
    console.print()
    console.print(render_anchors(messages, console))
    console.print()
