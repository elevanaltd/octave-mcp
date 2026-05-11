import unittest

from octave_mcp.core.emitter import emit
from octave_mcp.core.grammar.cst import Assignment, Document
from octave_mcp.core.parser import ParserError, parse


class TestConstrainedBreakthrough(unittest.TestCase):
    def test_emitter_dotted_identifier(self):
        """Test that dotted identifiers are NOT quoted."""
        doc = Document(name="TEST")
        # pkg.tool::value
        doc.sections.append(Assignment(key="pkg.tool", value="value"))

        output = emit(doc)
        print("\n--- Emitter Output ---")
        print(output)
        print("----------------------")

        # Verify it is NOT quoted as "pkg.tool"
        self.assertIn("pkg.tool::", output)
        self.assertNotIn('"pkg.tool"::', output)

    def test_parser_actionable_error(self):
        """Test that the parser gives an actionable E001 error."""
        content = """===TEST===
Invalid: Value
===END==="""

        print("\n--- Parser Error Test ---")
        try:
            parse(content)
            self.fail("Should have raised ParserError")
        except ParserError as e:
            print(f"Caught expected error: {e}")
            self.assertIn("Single colon assignment detected: 'Invalid: Value'", str(e))
            self.assertIn("OCTAVE REQUIREMENT: Use 'Invalid::Value'", str(e))


if __name__ == "__main__":
    unittest.main()
