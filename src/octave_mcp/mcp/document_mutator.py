"""DocumentMutator — the domain-mutation layer for changes-mode (GH#487 / STRATEGY_S3).

The root architectural pattern this module closes is ``ABSENT_DOMAIN_MUTATION_LAYER``:
STRATEGY_S1 split ``write.py`` into peer modules, but the *transition logic* (Q1 full
replace, Defect-2 scalar<->BLOCK resolution, MERGE-vs-REPLACE discrimination) and the
structural *AST synthesis* (constructing ``dirty=True`` Block / Assignment nodes) were
still latent and scattered across ``write.py:_apply_changes`` and ``write_mutation.py``.

The SEAM (CDV R2 anti-drift):
  - ``DocumentMutator`` OWNS transition logic + structural AST synthesis. It produces a
    mutated ``Document`` whose changed subtrees are born-/marked-``dirty`` AST nodes
    carrying only semantic content (key, children, value) and the dirty flags. It NEVER
    produces bytes and NEVER computes indentation.
  - The emitter (``core/emitter.py``, driven by ``write_format.py`` Strategy A) remains the
    SOLE canonicalizer-to-bytes. ``emit_block`` / ``emit_assignment`` derive indentation
    purely from recursion depth, so a born-dirty synthetic ``Block`` emits with correct
    indentation *by construction* — no node indentation metadata is required.

B-1 (this commit) is a PURE RELOCATION: the per-key body of ``WriteTool._apply_changes``
moved behind ``DocumentMutator.apply_change`` with ZERO behaviour change. The
``DocumentMutator`` delegates back to the owning ``WriteTool`` for path-resolution helpers
(``_find_block``, ``_apply_block_change``, ``_apply_section_change``, ``_is_anchored_change``,
``_resolve_anchored_change``) that remain on the tool. Subsequent commits (B-2..B-6) flip the
semantic behaviours behind this single API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from octave_mcp.core.grammar.cst import (
    Assignment,
    Block,
    Section,
)
from octave_mcp.mcp.write_mutation import (
    _SECTION_PATH_RE,
    _apply_array_op_inplace,
    _extract_op_descriptor,
    _is_delete_sentinel,
    _is_op_descriptor,
    _mark_dirty,
    _normalize_value_for_ast,
    _normalize_value_for_ast_preserving,
)

if TYPE_CHECKING:
    from octave_mcp.mcp.write import WriteTool


class DocumentMutator:
    """Owns transition logic + structural AST synthesis for changes-mode.

    Emits ``dirty=True`` nodes; never produces bytes (the emitter owns canon).
    """

    def __init__(self, tool: WriteTool) -> None:
        # The owning WriteTool supplies path-resolution helpers that remain its
        # responsibility (block/section finding, anchored-path resolution).
        self._tool = tool

    def apply_change(self, doc: Any, key: str, new_value: Any) -> None:
        """Apply a single changes-mode key/value mutation to ``doc`` in place.

        This is the per-key body relocated verbatim from ``WriteTool._apply_changes``
        (B-1, no behaviour change). Path validation / fail-fast is still performed by
        the caller (``WriteTool._apply_changes`` runs ``_validate_change_paths`` first).
        """
        tool = self._tool

        # GH#353: Section-prefixed paths (§N.KEY or §N::NAME.KEY)
        if key.startswith("§"):
            match = _SECTION_PATH_RE.match(key)
            if match:
                section_id, section_name, child_key = match.groups()
                tool._apply_section_change(doc, key, section_id, section_name, child_key, new_value)
            # Invalid section paths already rejected by _validate_change_paths
            return

        # Check for dot-notation: META.FIELD
        if key.startswith("META."):
            # Extract the field name after "META."
            field_name = key[5:]  # Remove "META." prefix

            # GH #447: I3 (MIRROR_CONSTRAINT) + I1 (SYNTACTIC_FIDELITY)
            # mutate-in-place contract. When a META envelope was parsed
            # with FLAT-form atoms (no ``META:`` block prefix), the
            # parser puts each atom in ``doc.sections`` as a top-level
            # ``Assignment`` rather than into the ``doc.meta`` dict. The
            # original ``META.<field>`` resolver wrote unconditionally
            # to ``doc.meta`` which on emit produced a NEW canonical
            # ``META:`` block alongside the surviving flat atom —
            # duplicate-key, form switch, I3 violation. We must locate
            # the existing flat atom FIRST and mutate it in place;
            # only when no flat atom exists do we fall through to the
            # ``doc.meta`` dict path (preserving today's behaviour for
            # documents whose META is parsed into the dict).
            #
            # PR #449 CE REWORK BLOCKING #1: the flat-atom scan MUST be
            # constrained to the ``===META===`` envelope shape only.
            # ``META.<field>`` addresses the flat-atom inside an envelope
            # whose name is "META", NOT any top-level atom with the
            # matching key anywhere in the document. CE's repro showed
            # that without this constraint a document like
            # ``===DOC===\nSTATUS::content_status\n===END===`` would have
            # its DOC envelope's ``STATUS`` atom silently mutated by
            # ``changes={"META.STATUS": ...}`` -- a cross-envelope scope
            # leak. We gate the scan on ``doc.name == "META"`` so that
            # only true META envelopes participate in the flat-atom path.
            flat_idx: int | None = None
            if doc.name == "META":
                for idx, section in enumerate(doc.sections):
                    if isinstance(section, Assignment) and section.key == field_name:
                        flat_idx = idx
                        break

            if flat_idx is not None:
                if _is_delete_sentinel(new_value):
                    # Remove the flat top-level Assignment in place.
                    del doc.sections[flat_idx]
                    # PR #449 CE REWORK observation #4: the deletion
                    # mechanism is OMISSION -- removing the Assignment
                    # node from ``doc.sections`` means the emitter
                    # cannot re-emit what is no longer there. We also
                    # mark ``doc.dirty=True`` so the preserve-mode
                    # emitter cannot splice the now-stale baseline
                    # bytes for this envelope; instead it re-emits
                    # canonically, naturally skipping the deleted
                    # atom. (No section-emission consults
                    # ``doc.dirty`` directly; the flag fences the
                    # baseline-slice path in ``emit()`` instead.)
                    doc.dirty = True
                else:
                    # I1 (Syntactic Fidelity): normalise the value.
                    target_assignment = doc.sections[flat_idx]
                    assert isinstance(target_assignment, Assignment)
                    # #460 Case A: preserve literal-zone fence form in place.
                    target_assignment.value = _normalize_value_for_ast_preserving(new_value, target_assignment.value)
                    # PR-2 T6: paired-write — mark only this leaf
                    # dirty so the preserve-mode emitter re-emits
                    # just this atom and splices the rest of the
                    # envelope verbatim.
                    _mark_dirty(target_assignment)
            elif _is_delete_sentinel(new_value):
                # No flat atom; fall through to doc.meta dict deletion.
                if field_name in doc.meta:
                    del doc.meta[field_name]
                # PR-2 T6: per-key META dirty map captures the
                # deletion event so PR-3's emitter knows this META
                # key no longer exists in the AST.
                doc.meta_dirty[field_name] = True
            else:
                # Update or add field in doc.meta
                # I1 (Syntactic Fidelity): Normalize Python values to AST types
                # Without this, Python lists emit as "['a', 'b']" instead of "[a,b]"
                doc.meta[field_name] = _normalize_value_for_ast(new_value)
                # PR-2 T6: paired-write — mark per-key dirty so PR-3
                # emitter re-emits only this META key and splices
                # the rest of META verbatim.
                doc.meta_dirty[field_name] = True
            return

        if key == "META" and isinstance(new_value, dict):
            if _is_delete_sentinel(new_value):
                # DELETE sentinel on META clears the entire block
                doc.meta = {}
                # PR-2 T6: whole-META clear -> mark every existing
                # key in meta_dirty so PR-3 emitter knows no key
                # survives. Use a sentinel "*" to denote whole-meta
                # dirty WITHOUT inventing a key shape that doesn't
                # match observable data. We instead mark
                # ``doc.dirty=True`` for whole-doc re-emit; the
                # per-key map remains the precision instrument.
                doc.dirty = True
            else:
                # GH#302: MERGE into existing META, not replace.
                # Previous behavior replaced the entire META dict, silently
                # dropping fields like CONTRACT::HOLOGRAPHIC that were not
                # included in the changes dict.  Merge preserves unmentioned
                # fields (I3 Mirror Constraint: reflect only present, create
                # nothing -- and do not destroy what is already present).
                #
                # GH#373: An explicit {"$op": "MERGE", "value": {...}} descriptor
                # has the same semantics as the bare-dict legacy form; payload
                # is the inner dict.
                op_meta, payload_meta, _ = _extract_op_descriptor(new_value)
                merge_dict = payload_meta if op_meta == "MERGE" else new_value
                for mk, mv in merge_dict.items():
                    if _is_delete_sentinel(mv):
                        doc.meta.pop(mk, None)
                        # PR-2 T6: per-key META dirty (deletion).
                        doc.meta_dirty[mk] = True
                    else:
                        # I1 (Syntactic Fidelity): Normalize values for AST
                        doc.meta[mk] = _normalize_value_for_ast(mv)
                        # PR-2 T6: paired-write — only touched keys
                        # are marked dirty; unmentioned META keys
                        # stay clean per the sibling-clean invariant
                        # (ADR §4 per-key dirty model).
                        doc.meta_dirty[mk] = True
            return

        if (
            "." in key
            and key.count(".") == 1
            and tool._find_block(doc, key.split(".", 1)[0]) is not None
            and not any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
        ):
            # GH#369: PARENT.CHILD where PARENT is a top-level Block and the
            # literal dotted key does NOT already exist as a flat top-level
            # Assignment. Route into the Block instead of falling through to
            # the flat-assignment branch (which would silently append a
            # duplicate assignment with a dotted key, violating I3).
            #
            # The "literal dotted key already exists at top level" check
            # preserves the GH#347 edge case where a block named e.g. "P1"
            # coexists with a flat assignment "P1.1::value": we still
            # modify the flat assignment in that scenario.
            parent_key, _, child_key = key.partition(".")
            tool._apply_block_change(doc, key, parent_key, child_key, new_value)
            return

        if _is_delete_sentinel(new_value) and not tool._is_anchored_change(doc, key):
            # I2: DELETE sentinel - remove field entirely from sections.
            # #460 Case B (rework B2): the bare-DELETE branch matches by
            # ``s.key == key`` and never matches an anchored path, so it
            # must NOT consume a resolvable ANCHOR/KEY DELETE (which would
            # otherwise silent-success no-op). Suppressing it for exactly
            # the keys the anchored branch claims (_is_anchored_change)
            # lets a resolvable anchored DELETE fall through to the
            # anchored handler below; a literal ``A/B`` key (resolve-
            # literal-first) is still handled here.
            doc.sections = [s for s in doc.sections if not (isinstance(s, Assignment) and s.key == key)]
            # PR-2 T6: doc.sections list changed (deletion). The
            # Document does not carry body_dirty; mark whole-doc
            # dirty so PR-3 emitter knows the sections list shape
            # differs from baseline. The other clean sections
            # still slice individually via their own dirty=False
            # spans.
            doc.dirty = True
            return

        if isinstance(new_value, dict) and not _is_op_descriptor(new_value) and tool._find_block(doc, key) is not None:
            # ADR-0006 SR2-T2 PR-2 (GH#377) T7: bare ``{KEY: {child:
            # v2}}`` change against an EXISTING top-level Block.
            # Without this branch, the dict would be normalised to
            # an InlineMap and appended as a NEW top-level
            # Assignment beside the Block (duplicate key, silent
            # shape switch — I3 violation under format_style
            # ``"preserve"``). With this branch, the dict is
            # expanded into per-child Assignment mutations against
            # the existing Block, keeping the Block shape and
            # marking only the touched children dirty.
            t7_block = tool._find_block(doc, key)
            assert t7_block is not None  # narrowed by branch guard
            for mk, mv in new_value.items():
                if _is_delete_sentinel(mv):
                    t7_block.children = [
                        c for c in t7_block.children if not (isinstance(c, Assignment) and c.key == mk)
                    ]
                    _mark_dirty(t7_block, body=True)
                    continue
                found_child = False
                for child in t7_block.children:
                    if isinstance(child, Assignment) and child.key == mk:
                        # #460 Case A: preserve literal-zone fence form in place.
                        child.value = _normalize_value_for_ast_preserving(mv, child.value)
                        _mark_dirty(child)
                        found_child = True
                        break
                if not found_child:
                    new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                    t7_block.children.append(new_child)
                _mark_dirty(t7_block, body=True)
            return

        if tool._is_anchored_change(doc, key):
            # #460 Case B: ANCHOR/KEY anchored-path. Resolve-literal-first —
            # _is_anchored_change is True only when no literal top-level
            # Assignment matches the raw key verbatim (that case is handled
            # by the legacy branch, preserving backward-compat for real keys
            # containing '/'). The same predicate gates the bare-DELETE
            # suppression above, keeping the two branches in lock-step.
            resolved = tool._resolve_anchored_change(doc, key)
            assert resolved is not None  # narrowed by _is_anchored_change
            target_assignment, parent = resolved
            # #460 (cubic P1): the anchored target is an Assignment, so it
            # MUST go through the SAME op machinery as a bare top-level key.
            # Otherwise a $op descriptor is normalized and written as literal
            # data (PROD::I3 violation: control descriptors as content).
            op, payload, _ = _extract_op_descriptor(new_value)
            if op == "DELETE" or _is_delete_sentinel(new_value):
                # Remove the resolved sibling from its parent's child list.
                if parent is None:
                    doc.sections = [s for s in doc.sections if s is not target_assignment]
                    doc.dirty = True
                elif isinstance(parent, (Block, Section)):
                    parent.children = [c for c in parent.children if c is not target_assignment]
                    _mark_dirty(parent, body=True)
            elif op in ("APPEND", "PREPEND"):
                # Array op on the resolved Assignment. _validate_change_paths
                # has already verified the target is array-typed via
                # _resolve_target_type (which resolves anchored paths), so a
                # type mismatch surfaces as E_OP_TARGET_MISMATCH before apply.
                _apply_array_op_inplace(target_assignment, op, payload)
                if isinstance(parent, (Block, Section)):
                    _mark_dirty(parent, body=True)
            elif op == "MERGE":
                # An anchored path resolves only to an Assignment, never a
                # Block/Section/META, so MERGE has no valid anchored target.
                # The validator rejects this upstream (E_OP_TARGET_MISMATCH);
                # this is a defensive loud failure so a MERGE descriptor can
                # NEVER be written as literal data if it ever reaches apply.
                raise ValueError(
                    [
                        {
                            "code": "E_OP_TARGET_MISMATCH",
                            "message": (
                                f"$op MERGE is not supported on anchored path '{key}': "
                                f"it resolves to an assignment (scalar/array), not a "
                                f"Block/Section/META target. MERGE only applies to "
                                f"top-level Blocks, Sections, or META."
                            ),
                        }
                    ]
                )
            else:
                # Bare value: full replacement.
                # #460 Case A interplay: preserve literal-zone fence form.
                target_assignment.value = _normalize_value_for_ast_preserving(new_value, target_assignment.value)
                _mark_dirty(target_assignment)
                if isinstance(parent, (Block, Section)):
                    _mark_dirty(parent, body=True)
            return

        # GH#373: Op-aware dispatch on top-level keys.
        # MERGE on a top-level Block; APPEND/PREPEND on a top-level
        # array Assignment. Bare values fall through to legacy
        # full-replacement.
        op, payload, _ = _extract_op_descriptor(new_value)

        if op == "MERGE":
            # Validator restricts MERGE to block/section/meta targets.
            target_block: Block | None = tool._find_block(doc, key)
            if target_block is not None:
                for mk, mv in payload.items():
                    if _is_delete_sentinel(mv):
                        target_block.children = [
                            c for c in target_block.children if not (isinstance(c, Assignment) and c.key == mk)
                        ]
                        _mark_dirty(target_block, body=True)
                        continue
                    found_child = False
                    for child in target_block.children:
                        if isinstance(child, Assignment) and child.key == mk:
                            # #460 Case A: preserve literal-zone fence form
                            # when MERGE replaces an existing fenced child.
                            child.value = _normalize_value_for_ast_preserving(mv, child.value)
                            # PR-2 T6: paired-write per leaf.
                            _mark_dirty(child)
                            found_child = True
                            break
                    if not found_child:
                        # New child: nothing to preserve, plain normalize.
                        new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                        target_block.children.append(new_child)
                    # PR-2 T6: in every MERGE-on-Block branch
                    # (existing-child mutate or new-child
                    # append), the block's body region changed.
                    _mark_dirty(target_block, body=True)
                return

            # MERGE on a Section -- search and merge children.
            target_section: Section | None = None
            for node in doc.sections:
                if isinstance(node, Section) and node.key == key:
                    target_section = node
                    break
            if target_section is not None:
                for mk, mv in payload.items():
                    if _is_delete_sentinel(mv):
                        target_section.children = [
                            c for c in target_section.children if not (isinstance(c, Assignment) and c.key == mk)
                        ]
                        _mark_dirty(target_section, body=True)
                        continue
                    found_child = False
                    for child in target_section.children:
                        if isinstance(child, Assignment) and child.key == mk:
                            # #460 Case A: preserve literal-zone fence form
                            # when MERGE replaces an existing fenced child.
                            child.value = _normalize_value_for_ast_preserving(mv, child.value)
                            _mark_dirty(child)
                            found_child = True
                            break
                    if not found_child:
                        # New child: nothing to preserve, plain normalize.
                        new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                        target_section.children.append(new_child)
                    _mark_dirty(target_section, body=True)
                return
            # Validator should have caught missing target; safety net.
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (f"$op MERGE target '{key}' not found as a Block " f"or Section."),
                    }
                ]
            )

        if op in ("APPEND", "PREPEND"):
            for section in doc.sections:
                if isinstance(section, Assignment) and section.key == key:
                    _apply_array_op_inplace(section, op, payload)
                    break
            else:
                raise ValueError(
                    [
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (f"$op {op} target '{key}' not found as a " f"top-level Assignment."),
                        }
                    ]
                )
            return

        # Legacy full-value replacement (or new Assignment if missing).
        # I1 (Syntactic Fidelity): Normalize Python values to AST types
        found = False
        for section in doc.sections:
            if isinstance(section, Assignment) and section.key == key:
                # #460 Case A: preserve literal-zone fence form in place.
                section.value = _normalize_value_for_ast_preserving(new_value, section.value)
                # PR-2 T6: paired-write on top-level Assignment.
                _mark_dirty(section)
                found = True
                break

        # If not found and not deleting, add new field
        if not found:
            # Create new assignment node with normalized value.
            # PR-2 T6: new Assignment is born dirty (no source
            # bytes to splice; its value MUST be re-emitted).
            new_assignment = Assignment(key=key, value=_normalize_value_for_ast(new_value), dirty=True)
            doc.sections.append(new_assignment)
