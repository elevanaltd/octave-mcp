"""P2-8b2 remainder: pith-spec.md amendments by record (guards written before the content change).

Records: OCTAVE-MCP-P2-8B-KERNELS-AND-SPLIT-RULINGS-20261106 (kernel bullet) and
PITH-PEER-MESSAGE-SHAPE-20261108 (Peer message shape bullet, SHAPE_TEXT verbatim).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "src/octave_mcp/resources/specs/pith-spec.md"

KERNEL_BULLET = (
    "Each kernel carries the standard items in full while any kernel-only consumer exists "
    "(OCTAVE-MCP-P2-8B-KERNELS-AND-SPLIT-RULINGS-20261106); a pointer alone would deliver no PITH to a "
    "kernel-only load. Compile-time de-duplication is not built; token limits are raised before content is cut."
)

# PITH-PEER-MESSAGE-SHAPE-20261108 fields.SHAPE_TEXT, verbatim.
PEER_SHAPE_TEXT = (
    "Peer message. One session to another through `SendMessage`; no envelope, no checker; dispatch bodies and "
    "replies stay Handoff. First line: one sentence that stands alone, the request or the fact itself, saying "
    "whether a reply is wanted; no sender preamble. Request: the first line is the `ASK` slot, written once, and "
    "names what the reply must contain; after it, only the other Handoff slots that have something to say, in "
    "Handoff order; a standing warning, an exclusion or an omission in the source is never dropped with its slot. "
    "Report: each fact with how it is known; a pointer in place of restated evidence only where the receiver can "
    "open it, otherwise the evidence. Relay of an operator ruling: the words verbatim with their conditions, "
    "session and date, marked relayed; it informs what was decided, and an operator-gated, irreversible or "
    "outward-facing act still needs authorisation in the receiving session. Acknowledgement: sent when the sender "
    "asked for one or when it changes what the sender does next; one line; no echo. A sender that needs "
    "confirmation asks for it in the first line."
)


def _lines() -> list[str]:
    return SPEC_PATH.read_text(encoding="utf-8").split("\n")


def _section(heading: str) -> list[str]:
    out: list[str] = []
    inside = False
    for line in _lines():
        if line.startswith("## "):
            inside = line[3:].strip().startswith(heading)
            continue
        if inside:
            out.append(line)
    return out


def test_kernel_bullet_is_the_ratified_text_verbatim() -> None:
    bullets = [ln[2:] for ln in _section("Skill kernels") if ln.startswith("- ")]
    assert KERNEL_BULLET in bullets, "the kernels bullet is not the 20261106 ruling text verbatim"


def test_kernel_bullet_has_no_trimmed_to_a_pointer_promise() -> None:
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert "Until the kernels are trimmed" not in text, "stale promise: kernels trimmed to a pointer"


def test_shapes_section_carries_the_peer_message_bullet_once_verbatim() -> None:
    bullets = [ln[2:] for ln in _section("Shapes") if ln.startswith("- ")]
    assert bullets.count(PEER_SHAPE_TEXT) == 1, "Shapes lacks the PITH-PEER-MESSAGE-SHAPE-20261108 bullet verbatim"
    assert len([b for b in bullets if b.startswith("Peer message.")]) == 1


def test_peer_bullet_is_placed_after_handoff_and_handoff_is_unchanged() -> None:
    bullets = [ln[2:] for ln in _section("Shapes") if ln.startswith("- ")]
    handoff = [i for i, b in enumerate(bullets) if b.startswith("Handoff. ")]
    peer = [i for i, b in enumerate(bullets) if b.startswith("Peer message.")]
    assert handoff and peer and peer[0] > handoff[0]
    assert "Seven slots in order: ASK, FROM, DECIDED, OUT_OF_SCOPE, DONE, UNCLEAR, LEFT_OUT" in bullets[handoff[0]]
