"""Tests for GH#246: Numbered-key syntax inside list literals.

When numbered-key syntax (e.g., 1::"string value") is used inside a list literal,
the canonicaliser must preserve the key::value association rather than flattening
the tokens into separate list items.

This is a violation of I1 (Syntactic Fidelity) and I3 (Mirror Constraint) when
the canonicaliser splits numbered-key items into separate tokens.
"""

from octave_mcp.core.ast_nodes import InlineMap, ListValue
from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestNumberedKeyInList:
    """GH#246: Numbered-key syntax inside list literals."""

    def test_numbered_key_list_roundtrip(self):
        """Numbered-key items in a list should survive parse->emit round-trip.

        Input: GATES::[1::"Strengthens?", 2::"Increases?", 3::"Protects?"]
        Expected: Items preserved as key::value pairs, not flattened.
        """
        input_text = '===TEST===\nGATES::[\n  1::"Strengthens Elevana as infrastructure?",\n  2::"Increases long-term integration?",\n  3::"Protects asset value?"\n]\n===END===\n'

        doc = parse(input_text)
        output = emit(doc)

        # The canonical output must NOT contain the flattened form
        assert '"::","Strengthens' not in output, "Bug #246: numbered-key items were flattened into separate tokens"

        # The canonical output MUST preserve the numbered-key association
        assert '1::"Strengthens Elevana as infrastructure?"' in output
        assert '2::"Increases long-term integration?"' in output
        assert '3::"Protects asset value?"' in output

    def test_numbered_key_parsed_as_inline_map(self):
        """Numbered keys inside list should parse as InlineMap items, not bare values."""
        input_text = '===TEST===\nITEMS::[1::"first", 2::"second"]\n===END===\n'

        doc = parse(input_text)

        # Find the ITEMS assignment
        items_assignment = doc.sections[0]
        assert items_assignment.key == "ITEMS"

        list_value = items_assignment.value
        assert isinstance(list_value, ListValue)

        # Each item should be an InlineMap, not a bare number/string
        assert len(list_value.items) == 2, f"Expected 2 items but got {len(list_value.items)}: {list_value.items}"

        for item in list_value.items:
            assert isinstance(item, InlineMap), f"Expected InlineMap but got {type(item).__name__}: {item!r}"

    def test_numbered_key_values_preserved(self):
        """The key and value of each numbered-key pair should be correct."""
        input_text = '===TEST===\nITEMS::[1::"alpha", 2::"beta", 3::"gamma"]\n===END===\n'

        doc = parse(input_text)
        list_value = doc.sections[0].value
        assert isinstance(list_value, ListValue)

        # Check each item
        expected = [("1", "alpha"), ("2", "beta"), ("3", "gamma")]
        for i, (exp_key, exp_val) in enumerate(expected):
            item = list_value.items[i]
            assert isinstance(item, InlineMap)
            assert exp_key in item.pairs, f"Expected key '{exp_key}' in item {i}"
            assert (
                item.pairs[exp_key] == exp_val
            ), f"Expected value '{exp_val}' for key '{exp_key}' but got '{item.pairs[exp_key]}'"

    def test_single_numbered_key_in_list(self):
        """A single numbered-key item in a list should work."""
        input_text = '===TEST===\nSINGLE::[1::"only item"]\n===END===\n'

        doc = parse(input_text)
        output = emit(doc)

        assert '1::"only item"' in output

    def test_numbered_key_idempotent(self):
        """Parse->emit->parse->emit should be idempotent for numbered-key lists."""
        input_text = '===TEST===\nGATES::[\n  1::"Strengthens?",\n  2::"Increases?",\n  3::"Protects?"\n]\n===END===\n'

        doc1 = parse(input_text)
        output1 = emit(doc1)

        doc2 = parse(output1)
        output2 = emit(doc2)

        assert output1 == output2, f"Not idempotent.\nFirst emit:\n{output1}\nSecond emit:\n{output2}"

    def test_mixed_numbered_keys_and_regular_items(self):
        """A list can contain both numbered-key items and regular values."""
        input_text = '===TEST===\nMIXED::[1::"numbered", regular_value, 2::"also numbered"]\n===END===\n'

        doc = parse(input_text)
        list_value = doc.sections[0].value
        assert isinstance(list_value, ListValue)

        assert len(list_value.items) == 3
        assert isinstance(list_value.items[0], InlineMap)
        assert list_value.items[1] == "regular_value"
        assert isinstance(list_value.items[2], InlineMap)
