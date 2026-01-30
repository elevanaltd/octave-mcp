===EMOJI_IDENTIFIERS===
META:
  TYPE::TEST_VECTOR
  VERSION::"1.0.0"
  PURPOSE::"Validates emoji and unicode symbol support in identifiers per GH#186"
  REFERENCE::"lexer.py _is_valid_identifier_start/char() lines 129-214"

---

// GH#186: Unicode characters valid in identifiers
// Categories: L* (letters), So (symbols), Sm (math), No (numbers), Sk (modifiers), Po (punctuation)

// Simple emoji as keys (category So - Symbol Other)
✓::check_mark
⚠::warning_sign
🔥::fire_indicator
🚀::rocket_status
✅::green_check
❌::red_x
⭐::star_rating
💡::idea_indicator

// Mathematical symbols (category Sm - excluding OCTAVE operators)
// Note: ⊕ (U+2295), ∧ (U+2227), ∨ (U+2228), → (U+2192), ⇌ (U+21CC), § (U+00A7), ⧺ (U+29FA) are EXCLUDED
∞::infinity_indicator
≈::approx_equal
∑::sum_indicator
∏::product_indicator
√::square_root

// Box drawing and misc symbols (category So)
•::bullet_point
★::star_marker
◆::diamond_marker
►::arrow_right
◉::circle_filled

// Unicode letters from various scripts (category L*)
Привет::cyrillic_text
α::greek_alpha
β::greek_beta
λ::lambda_symbol
日本語::japanese_text

// Mixed emoji and ASCII identifiers
STATUS_✓::completed
ALERT_⚠::active
PRIORITY_⭐::high
🔥_URGENT::critical
TEST_✅_PASS::success

// Emoji in list context
EMOJI_LIST::[✓, ⚠, 🔥, 🚀]

// Emoji as section content (using block syntax, not section marker)
INDICATORS:
  ✓_SUCCESS::pass
  ❌_FAILURE::fail
  ⏳_PENDING::wait
  🛑_BLOCKED::stop

// Number forms (category No - Number Other)
// Note: Roman numerals (category Nl) are NOT supported, only circled numbers
①::circled_one
②::circled_two
③::circled_three
④::circled_four
⑤::circled_five

// Modifier symbols (category Sk)
// Note: Many Sk symbols are diacritics, using combining circumflex as example
CARET_SYMBOL::caret

===END===
