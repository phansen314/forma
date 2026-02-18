#!/usr/bin/env python3
"""Tests for forma_parser.py and validate.py.

Run from any directory:
    python tools/test_forma.py
"""

import sys
import unittest
from pathlib import Path

# Ensure tools dir is importable
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from forma_parser import parse_forma, LexError, ParseError
from validate import ModelValidator


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestLexer(unittest.TestCase):
    """Token-level tests."""

    def test_empty_file(self):
        ir = parse_forma("")
        self.assertEqual(ir, {})

    def test_line_comment_stripped(self):
        ir = parse_forma("// just a comment\n")
        self.assertEqual(ir, {})

    def test_block_comment_stripped(self):
        ir = parse_forma("/* block */")
        self.assertEqual(ir, {})

    def test_nested_block_comment(self):
        ir = parse_forma("/* outer /* inner */ still outer */")
        self.assertEqual(ir, {})

    def test_unterminated_block_comment(self):
        with self.assertRaises(LexError):
            parse_forma("/* unterminated")

    def test_unterminated_string(self):
        with self.assertRaises(LexError):
            parse_forma('(model Foo v1.0 "unterminated)')

    def test_unexpected_character(self):
        with self.assertRaises(LexError):
            parse_forma("@")

    def test_string_escape_sequences(self):
        ir = parse_forma('(model Foo v1.0 "line1\\nline2\\ttab")')
        self.assertEqual(ir["meta"]["description"], "line1\nline2\ttab")


class TestParserModel(unittest.TestCase):
    """Model declaration parsing."""

    def test_model_basic(self):
        ir = parse_forma('(model Foo v1.0 "A description")')
        self.assertEqual(ir["meta"]["name"], "Foo")
        self.assertEqual(ir["meta"]["version"], "1.0")
        self.assertEqual(ir["meta"]["description"], "A description")

    def test_model_no_description(self):
        ir = parse_forma("(model Foo v2.5)")
        self.assertEqual(ir["meta"]["name"], "Foo")
        self.assertEqual(ir["meta"]["version"], "2.5")
        self.assertNotIn("description", ir["meta"])

    def test_model_version_strips_v(self):
        ir = parse_forma("(model Foo v8.0)")
        self.assertEqual(ir["meta"]["version"], "8.0")


class TestParserNamespace(unittest.TestCase):
    """Namespace declaration parsing."""

    def test_namespace(self):
        ir = parse_forma("(namespace com.example.foo)\n(model X v1.0)")
        self.assertEqual(ir["meta"]["namespace"], "com.example.foo")

    def test_duplicate_namespace(self):
        with self.assertRaises(ParseError):
            parse_forma("(namespace a.b)\n(namespace c.d)")


class TestParserShapes(unittest.TestCase):
    """Shape parsing."""

    def test_simple_shape(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo name: string age: int)")
        self.assertIn("Foo", ir["shapes"])
        self.assertEqual(ir["shapes"]["Foo"]["fields"], {"name": "string", "age": "int"})

    def test_shape_with_mixin(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixin M x: int)\n"
            "(shape Foo [M] y: string)"
        )
        self.assertEqual(ir["shapes"]["Foo"]["use"], ["M"])
        self.assertEqual(ir["shapes"]["Foo"]["fields"], {"y": "string"})

    def test_shape_with_generic_mixin(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixin V<T> current: T)\n"
            "(shape Foo [V<Bird>] name: string)"
        )
        self.assertEqual(ir["shapes"]["Foo"]["use"], ["V<Bird>"])

    def test_shape_nullable_field(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo x: string?)")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["x"], "string?")

    def test_shape_collection_field(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo items: [string])")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["items"], "[string]")

    def test_shape_association_field(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo meta: {string, json})")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["meta"], "{string, json}")

    def test_shape_named_wrapper(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo tree: tree<Category>)")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["tree"], "tree<Category>")

    def test_nullable_collection(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo items: [string]?)")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["items"], "[string]?")

    def test_nullable_association(self):
        ir = parse_forma("(model T v1.0)\n(shape Foo meta: {string, json}?)")
        self.assertEqual(ir["shapes"]["Foo"]["fields"]["meta"], "{string, json}?")


class TestParserPluralShapes(unittest.TestCase):
    """Plural shape form."""

    def test_shapes_plural(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(shapes\n"
            "  (Foo x: int)\n"
            "  (Bar y: string))"
        )
        self.assertIn("Foo", ir["shapes"])
        self.assertIn("Bar", ir["shapes"])

    def test_shapes_plural_with_mixin(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixin M z: bool)\n"
            "(shapes\n"
            "  (Foo [M] x: int))"
        )
        self.assertEqual(ir["shapes"]["Foo"]["use"], ["M"])


class TestParserChoices(unittest.TestCase):
    """Choice parsing."""

    def test_enum_like(self):
        ir = parse_forma("(model T v1.0)\n(choice Color red green blue)")
        self.assertIn("Color", ir["choices"])
        self.assertEqual(set(ir["choices"]["Color"].keys()), {"red", "green", "blue"})
        for v in ir["choices"]["Color"].values():
            self.assertEqual(v, {})

    def test_fielded_choice(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(choice Payment\n"
            "  (common amount: float)\n"
            "  (Card number: string)\n"
            "  Cash)"
        )
        choice = ir["choices"]["Payment"]
        self.assertEqual(choice["common"], {"amount": "float"})
        self.assertEqual(choice["Card"], {"number": "string"})
        self.assertEqual(choice["Cash"], {})

    def test_choices_plural(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(choices\n"
            "  (Color red green blue)\n"
            "  (Size small medium large))"
        )
        self.assertIn("Color", ir["choices"])
        self.assertIn("Size", ir["choices"])


class TestParserMixins(unittest.TestCase):
    """Mixin parsing."""

    def test_simple_mixin(self):
        ir = parse_forma("(model T v1.0)\n(mixin M x: int y: string)")
        self.assertIn("M", ir["mixins"])
        self.assertEqual(ir["mixins"]["M"]["fields"], {"x": "int", "y": "string"})
        self.assertNotIn("type_params", ir["mixins"]["M"])

    def test_generic_mixin(self):
        ir = parse_forma("(model T v1.0)\n(mixin V<T> current: T history: [T])")
        self.assertEqual(ir["mixins"]["V"]["type_params"], ["T"])
        self.assertEqual(ir["mixins"]["V"]["fields"]["current"], "T")

    def test_multi_param_mixin(self):
        ir = parse_forma("(model T v1.0)\n(mixin Pair<A, B> first: A second: B)")
        self.assertEqual(ir["mixins"]["Pair"]["type_params"], ["A", "B"])

    def test_mixin_composition(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixin A x: int)\n"
            "(mixin B [A] y: string)"
        )
        self.assertEqual(ir["mixins"]["B"]["use"], ["A"])

    def test_mixins_plural(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixins\n"
            "  (A x: int)\n"
            "  (B<T> [A] y: T))"
        )
        self.assertIn("A", ir["mixins"])
        self.assertIn("B", ir["mixins"])
        self.assertEqual(ir["mixins"]["B"]["type_params"], ["T"])
        self.assertEqual(ir["mixins"]["B"]["use"], ["A"])


class TestParserMixed(unittest.TestCase):
    """Mixed singular and plural forms."""

    def test_singular_and_plural(self):
        ir = parse_forma(
            "(model T v1.0)\n"
            "(mixin A x: int)\n"
            "(shapes\n"
            "  (Foo [A] y: string)\n"
            "  (Bar z: bool))\n"
            "(shape Baz w: float)\n"
            "(choice Color red green blue)"
        )
        self.assertEqual(len(ir["shapes"]), 3)
        self.assertIn("Color", ir["choices"])
        self.assertIn("A", ir["mixins"])


class TestParserErrors(unittest.TestCase):
    """Parser error conditions."""

    def test_missing_opening_paren(self):
        with self.assertRaises(ParseError):
            parse_forma("model Foo v1.0")

    def test_unknown_keyword(self):
        with self.assertRaises(ParseError):
            parse_forma("(foobar Baz)")

    def test_missing_closing_paren(self):
        with self.assertRaises(ParseError):
            parse_forma("(model Foo v1.0")


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

def _validate(source: str):
    """Parse and validate, returning (errors, warnings)."""
    ir = parse_forma(source)
    v = ModelValidator(ir)
    return v.validate()


def _error_codes(errors):
    return [e.code for e in errors]


def _warn_codes(warnings):
    return [w.code for w in warnings]


class TestValidatorMeta(unittest.TestCase):
    """Meta section validation."""

    def test_valid_model(self):
        errors, warnings = _validate('(model Foo v1.0 "desc")')
        self.assertEqual(errors, [])
        self.assertNotIn("W013", _warn_codes(warnings))

    def test_missing_meta(self):
        # Empty file has no meta
        errors, _ = _validate("")
        self.assertIn("E001", _error_codes(errors))

    def test_missing_description_warns(self):
        _, warnings = _validate("(model Foo v1.0)")
        self.assertIn("W013", _warn_codes(warnings))

    def test_invalid_namespace(self):
        # Parser won't produce an empty-string namespace, but we can test
        # the validator directly with a crafted IR
        v = ModelValidator({"meta": {"name": "X", "version": "1.0", "namespace": ""}})
        errors, _ = v.validate()
        self.assertIn("E004", _error_codes(errors))


class TestValidatorShapes(unittest.TestCase):
    """Shape validation."""

    def test_valid_shape(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(shape Foo x: string)'
        )
        self.assertEqual(errors, [])

    def test_shape_no_fields_error(self):
        # Craft IR directly since parser requires fields
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "shapes": {"Foo": {"fields": {}}}
        })
        errors, _ = v.validate()
        self.assertIn("E070", _error_codes(errors))

    def test_shape_unknown_mixin(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(shape Foo [NonExistent] x: int)'
        )
        self.assertIn("E084", _error_codes(errors))

    def test_shape_field_shadows_mixin(self):
        _, warnings = _validate(
            '(model T v1.0 "d")\n'
            '(mixin M x: int)\n'
            '(shape Foo [M] x: string)'
        )
        self.assertIn("W012", _warn_codes(warnings))

    def test_shape_mixin_arity_mismatch(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin V<T> current: T)\n'
            '(shape Foo [V] x: int)'
        )
        self.assertIn("E086", _error_codes(errors))

    def test_shape_mixin_not_generic_but_given_args(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin M x: int)\n'
            '(shape Foo [M<Bird>] y: string)'
        )
        self.assertIn("E086", _error_codes(errors))

    def test_shape_unknown_sub_key(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "shapes": {"Foo": {"fields": {"x": "int"}, "bogus": True}}
        })
        errors, _ = v.validate()
        self.assertIn("E085", _error_codes(errors))


class TestValidatorChoices(unittest.TestCase):
    """Choice validation."""

    def test_valid_enum_like(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(choice Color red green blue)'
        )
        self.assertEqual(errors, [])

    def test_choice_too_few_variants(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(choice Color red)'
        )
        self.assertIn("E050", _error_codes(errors))

    def test_valid_fielded_choice(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(choice Payment\n'
            '  (common amount: float)\n'
            '  (Card number: string)\n'
            '  Cash)'
        )
        self.assertEqual(errors, [])

    def test_empty_choices_section_warns(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "choices": {}
        })
        _, warnings = v.validate()
        self.assertIn("W017", _warn_codes(warnings))


class TestValidatorMixins(unittest.TestCase):
    """Mixin validation."""

    def test_valid_mixin(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(mixin M x: int)'
        )
        self.assertEqual(errors, [])

    def test_mixin_no_fields(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "mixins": {"M": {"fields": {}}}
        })
        errors, _ = v.validate()
        self.assertIn("E060", _error_codes(errors))

    def test_mixin_composition_valid(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin A x: int)\n'
            '(mixin B [A] y: string)'
        )
        self.assertEqual(errors, [])

    def test_mixin_circular_composition(self):
        # Can't create circular via parser, so craft IR
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "mixins": {
                "A": {"use": ["B"], "fields": {"x": "int"}},
                "B": {"use": ["A"], "fields": {"y": "string"}},
            }
        })
        errors, _ = v.validate()
        self.assertIn("E091", _error_codes(errors))

    def test_mixin_unknown_composition_ref(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin A [NonExistent] x: int)'
        )
        self.assertIn("E092", _error_codes(errors))

    def test_mixin_unknown_sub_key(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "mixins": {"M": {"fields": {"x": "int"}, "bogus": True}}
        })
        errors, _ = v.validate()
        self.assertIn("E060", _error_codes(errors))

    def test_empty_mixins_section_warns(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "mixins": {}
        })
        _, warnings = v.validate()
        self.assertIn("W017", _warn_codes(warnings))


class TestValidatorTypes(unittest.TestCase):
    """Type resolution validation."""

    def test_mixin_as_field_type(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin M x: int)\n'
            '(shape Foo y: M)'
        )
        self.assertIn("E042", _error_codes(errors))

    def test_atoms_are_valid(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n(shape Foo id: UUID name: string email: Email)'
        )
        self.assertEqual(errors, [])

    def test_named_wrapper_warns(self):
        _, warnings = _validate(
            '(model T v1.0 "d")\n(shape Foo tree: tree<string>)'
        )
        self.assertIn("W015", _warn_codes(warnings))

    def test_nullable_collection_element_warns(self):
        _, warnings = _validate(
            '(model T v1.0 "d")\n(shape Foo items: [string?])'
        )
        self.assertIn("W019", _warn_codes(warnings))

    def test_association_wrong_arity(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "shapes": {"Foo": {"fields": {"x": "{string}"}}}
        })
        errors, _ = v.validate()
        self.assertIn("E041", _error_codes(errors))


class TestValidatorDuplicates(unittest.TestCase):
    """Duplicate name detection."""

    def test_duplicate_across_sections(self):
        # Shape and choice with same name
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "shapes": {"Foo": {"fields": {"x": "int"}}},
            "choices": {"Foo": {"a": {}, "b": {}}}
        })
        errors, _ = v.validate()
        self.assertIn("E100", _error_codes(errors))

    def test_mixin_collides_with_shape(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "shapes": {"Foo": {"fields": {"x": "int"}}},
            "mixins": {"Foo": {"fields": {"y": "string"}}}
        })
        errors, _ = v.validate()
        self.assertIn("E100", _error_codes(errors))


class TestValidatorTopLevel(unittest.TestCase):
    """Top-level key validation."""

    def test_unknown_top_level_key(self):
        v = ModelValidator({
            "meta": {"name": "T", "version": "1.0"},
            "bogus": {}
        })
        errors, _ = v.validate()
        self.assertIn("E010", _error_codes(errors))


class TestValidatorMixinExpansion(unittest.TestCase):
    """Mixin field expansion in shapes."""

    def test_transitive_composition(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin A x: int)\n'
            '(mixin B [A] y: string)\n'
            '(shape Foo [B] z: bool)'
        )
        self.assertEqual(errors, [])

    def test_mixin_field_conflict(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin A x: int)\n'
            '(mixin B x: string)\n'
            '(shape Foo [A B] y: bool)'
        )
        self.assertIn("E090", _error_codes(errors))

    def test_generic_mixin_substitution(self):
        errors, _ = _validate(
            '(model T v1.0 "d")\n'
            '(mixin V<T> current: T history: [T])\n'
            '(shape Bird [V<Bird>] name: string)'
        )
        self.assertEqual(errors, [])


class TestValidatorBirdTracker(unittest.TestCase):
    """Validate the full BirdTracker example file."""

    def test_birdtracker_valid(self):
        example = Path(__file__).resolve().parent.parent.parent / "examples" / "birdtracker.forma"
        if not example.exists():
            self.skipTest(f"Example file not found: {example}")
        source = example.read_text(encoding="utf-8")
        errors, warnings = _validate(source)
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")


if __name__ == "__main__":
    unittest.main()
