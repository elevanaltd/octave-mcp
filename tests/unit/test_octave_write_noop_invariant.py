"""ADR-0006 SR1-T4 — octave_write no-op invariant on unchanged target.

Pre-release verification (v1.12.0) of an invariant that the Step 6
validator-surface collapse (PR #401) makes structurally likely to hold but
does not explicitly assert: when ``octave_write`` is invoked in normalize
mode (no ``content``, no ``changes``) against an *already-canonical*
target, the operation must be a no-op at the bytes/diff layer.

Invariant proven (per task SR1-T4, blocking conditions):

* I1 (Syntactic Fidelity) idempotence: canon(canon(x)) == canon(x). The
  bytes written must equal the bytes already on disk.
* I3 (Mirror Constraint): a no-op must not fabricate a non-empty diff or
  spurious correction entries; ``diff`` reports ``"No changes"``.
* Result envelope reports ``status == "success"``.

Out of scope (documented follow-up candidate, NOT blocking):

* Disk-write skip / mtime preservation. The current ``octave_write``
  implementation performs an atomic ``tempfile -> fsync -> os.replace``
  unconditionally (see ``src/octave_mcp/mcp/write.py`` STEP "WRITE FILE").
  An identical-bytes replace is wasteful but not a correctness failure
  (per SR1-T4 task constraint: "write happens but produces identical
  bytes — wasteful but not a correctness failure"). A short-circuit that
  skips ``os.replace`` when ``baseline_content_for_diff ==
  canonical_content`` would tighten this surface and is queued as a
  follow-up; it is intentionally NOT asserted here so that this test
  remains a pure correctness fence rather than a performance fence.

Fixture coverage (per SR1-T4 task: literal zones; META + body; trivia):

* ``literal_zones``  — exercises Zone-3 (literal zone) preservation under
  re-normalization.
* ``meta_and_body``  — exercises META frontmatter + Zone-1 normalizing
  DSL body.
* ``trivia``         — exercises trivia (blank lines, indentation,
  comments) survival under re-normalization. I4 may log trivia receipts
  on the FIRST normalize call; the invariant under test is the SECOND
  pass over already-canonical bytes, where no further normalization is
  legal.

TDD discipline: this test is intentionally written against the public
MCP entrypoint (``WriteTool().execute(...)``), not internal helpers, so
that the invariant binds at the surface that ships to consumers.
"""

from __future__ import annotations

import hashlib
import os
import tempfile

import pytest

# Representative inputs covering the three shapes called out by SR1-T4.
# These are not required to be canonical on first write — the test first
# canonicalizes them, then asserts the SECOND normalize pass is a no-op.
_LITERAL_ZONES_INPUT = """===LITERAL_ZONES_DOC===
META:
  TYPE::"EXAMPLE"
  VERSION::"1.0"

§1::BODY
DESCRIPTION::"Document with a fenced literal zone"

```python
def f(x):
    return x + 1
```

===END==="""


_META_AND_BODY_INPUT = """===META_BODY_DOC===
META:
  TYPE::"EXAMPLE"
  VERSION::"1.0"
  AUTHOR::"sr1-t4"

§1::BODY
KEY_ONE::"value one"
KEY_TWO::"value two"
NESTED:
  CHILD_A::"a"
  CHILD_B::"b"

===END==="""


_TRIVIA_INPUT = """===TRIVIA_DOC===
META:
  TYPE::"EXAMPLE"
  VERSION::"1.0"

// Top-level comment preceding the body
§1::BODY
// Inline comment before an assignment
KEY::"value"
ANOTHER_KEY::"another"

===END==="""


@pytest.mark.parametrize(
    "fixture_id, raw_input",
    [
        ("literal_zones", _LITERAL_ZONES_INPUT),
        ("meta_and_body", _META_AND_BODY_INPUT),
        ("trivia", _TRIVIA_INPUT),
    ],
)
@pytest.mark.asyncio
async def test_octave_write_noop_on_canonical_target(fixture_id: str, raw_input: str) -> None:
    """SR1-T4 invariant: octave_write on already-canonical bytes is a no-op.

    Procedure:
    1. Seed the file with ``raw_input`` and run a FIRST normalize pass to
       drive the bytes to canonical form. (The raw input may or may not
       already be canonical; we do not depend on it.)
    2. Capture the canonical bytes and their SHA-256.
    3. Run a SECOND normalize pass against the now-canonical file.
    4. Assert blocking invariants:
         - ``status == "success"``
         - bytes on disk are byte-identical to the post-step-2 canonical
         - structural diff reports ``"No changes"`` and ``diff_unified``
           contains no actual diff hunks (empty or whitespace-only)
         - ``canonical_hash`` matches the captured canonical hash
           (witnesses I1 idempotence)
    """
    # Local import to mirror existing test_write_tool.py style (lazy import).
    from octave_mcp.mcp.write import WriteTool

    tool = WriteTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, f"{fixture_id}.oct.md")
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(raw_input)

        # STEP 1: First pass — drive to canonical form. We do not assert
        # anything about this call other than that it succeeded; its job is
        # to give us a canonical baseline regardless of the raw input.
        seed_result = await tool.execute(target_path=target_path)
        assert seed_result["status"] == "success", (
            f"[{fixture_id}] precondition failed: first normalize pass did "
            f"not succeed — errors={seed_result.get('errors')!r}"
        )

        # STEP 2: Capture canonical bytes + hash.
        with open(target_path, "rb") as fb:
            canonical_bytes = fb.read()
        canonical_hash = hashlib.sha256(canonical_bytes).hexdigest()
        assert seed_result["canonical_hash"] == canonical_hash, (
            f"[{fixture_id}] result canonical_hash does not match on-disk "
            f"sha256 after first normalize pass — surface hash drift"
        )

        # STEP 3: Second pass — the invariant under test.
        result = await tool.execute(target_path=target_path)

        # STEP 4: Blocking assertions.

        # (a) Success envelope (no spurious errors invented by I3 mirror).
        assert result["status"] == "success", (
            f"[{fixture_id}] second normalize pass MUST succeed on "
            f"already-canonical input; got errors={result.get('errors')!r}"
        )

        # (b) I1 idempotence: bytes on disk are unchanged.
        with open(target_path, "rb") as fb:
            after_bytes = fb.read()
        assert after_bytes == canonical_bytes, (
            f"[{fixture_id}] I1 idempotence violated: re-normalizing "
            f"already-canonical bytes produced different bytes. "
            f"before_sha256={canonical_hash} "
            f"after_sha256={hashlib.sha256(after_bytes).hexdigest()}"
        )

        # (c) canonical_hash in the envelope still matches captured hash.
        assert result["canonical_hash"] == canonical_hash, (
            f"[{fixture_id}] envelope canonical_hash drifted between two "
            f"normalize passes over identical input: "
            f"first={canonical_hash} second={result['canonical_hash']}"
        )

        # (d) I3 mirror / zero-diff: structural diff says no changes, and
        # the unified diff contains no actual hunk lines. We allow the
        # unified-diff string to be empty or to be present-but-empty (no
        # ``@@`` hunks and no ``+``/``-`` body lines), since the diff
        # builder may emit a header even for identity inputs in some
        # implementations.
        assert result["diff"] == "No changes", (
            f"[{fixture_id}] I3 mirror violated: diff field reports " f"changes on a no-op — got {result['diff']!r}"
        )

        diff_unified = result.get("diff_unified", "") or ""
        hunk_lines = [
            line
            for line in diff_unified.splitlines()
            if line.startswith("@@") or line.startswith("+") or line.startswith("-")
        ]
        # Filter out the unified-diff file headers (+++/---) which are not
        # content hunks even when present.
        content_hunk_lines = [line for line in hunk_lines if not (line.startswith("+++") or line.startswith("---"))]
        assert not content_hunk_lines, (
            f"[{fixture_id}] diff_unified contains content hunks on a " f"no-op normalize: {content_hunk_lines!r}"
        )
