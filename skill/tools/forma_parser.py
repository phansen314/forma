#!/usr/bin/env python3
"""Forma DSL parser (S-expression syntax).

Parses .forma files into an IR dict that the ModelValidator can validate.

Grammar (EBNF):

    file           = { comment | form } EOF
    form           = "(" ( namespace_form | model_form
                         | mixin_form | mixins_form
                         | choice_form | choices_form
                         | shape_form | shapes_form ) ")"

    namespace_form = "namespace" IDENT
    model_form     = "model" IDENT version [ STRING ]
    version        = IDENT                          // e.g. v8.0
    mixin_form     = "mixin" IDENT [ "<" IDENT { "," IDENT } ">" ]
                     [ "[" mixin_ref { mixin_ref } "]" ] { field }
    mixins_form    = "mixins" { "(" IDENT [ "<" IDENT { "," IDENT } ">" ]
                     [ "[" mixin_ref { mixin_ref } "]" ] { field } ")" }
    choice_form    = "choice" IDENT { common_form | variant }
    choices_form   = "choices" { "(" IDENT { common_form | variant } ")" }
    shape_form     = "shape" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field }
    shapes_form    = "shapes" { "(" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field } ")" }
    common_form    = "(" "common" { field } ")"
    variant        = IDENT | "(" IDENT { field } ")"

    mixin_ref      = IDENT [ "<" type_expr { "," type_expr } ">" ]
    field          = IDENT ":" type_expr
    type_expr      = base_type [ "?" ]
    base_type      = IDENT [ "<" type_expr { "," type_expr } ">" ]
                   | "[" type_expr { "," type_expr } "]"
                   | "{" type_expr "," type_expr "}"

    comment        = "//" ... EOL
                   | "/*" ... "*/"          // nestable
    STRING         = '"' ... '"'
    IDENT          = letter { letter | digit | "_" | "." }

Usage:
    from forma_parser import parse_forma

    ir = parse_forma(source_text)
    # ir is a dict with keys: meta, shapes, choices, mixins
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------

class TT:
    """Token types."""
    EOF = "EOF"
    IDENT = "IDENT"
    STRING = "STRING"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    LANGLE = "<"
    RANGLE = ">"
    COLON = ":"
    COMMA = ","
    QUESTION = "?"


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"line {line}, col {col}: {message}")
        self.line = line
        self.col = col


def _lex(source: str) -> list[Token]:
    """Tokenize a .forma source string."""
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1

    while i < len(source):
        ch = source[i]

        # Newline
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue

        # Whitespace
        if ch in " \t\r":
            i += 1
            col += 1
            continue

        # Comments
        if ch == "/" and i + 1 < len(source):
            next_ch = source[i + 1]
            # Line comment: // ... EOL
            if next_ch == "/":
                while i < len(source) and source[i] != "\n":
                    i += 1
                continue
            # Block comment: /* ... */ (nestable)
            if next_ch == "*":
                start_line = line
                start_col = col
                i += 2; col += 2
                depth = 1
                while i < len(source) and depth > 0:
                    if source[i] == "/" and i + 1 < len(source) and source[i + 1] == "*":
                        depth += 1; i += 2; col += 2
                    elif source[i] == "*" and i + 1 < len(source) and source[i + 1] == "/":
                        depth -= 1; i += 2; col += 2
                    elif source[i] == "\n":
                        i += 1; line += 1; col = 1
                    else:
                        i += 1; col += 1
                if depth > 0:
                    raise LexError("unterminated block comment", start_line, start_col)
                continue

        # String literal
        if ch == '"':
            start_col = col
            i += 1
            col += 1
            buf = []
            while i < len(source) and source[i] != '"':
                if source[i] == "\n":
                    raise LexError("unterminated string literal", line, start_col)
                if source[i] == "\\" and i + 1 < len(source):
                    i += 1
                    col += 1
                    esc = source[i]
                    if esc == "n":
                        buf.append("\n")
                    elif esc == "t":
                        buf.append("\t")
                    elif esc == "\\":
                        buf.append("\\")
                    elif esc == '"':
                        buf.append('"')
                    else:
                        buf.append(esc)
                else:
                    buf.append(source[i])
                i += 1
                col += 1
            if i >= len(source):
                raise LexError("unterminated string literal", line, start_col)
            i += 1  # closing quote
            col += 1
            tokens.append(Token(TT.STRING, "".join(buf), line, start_col))
            continue

        # Single-character tokens
        singles = {
            "(": TT.LPAREN, ")": TT.RPAREN,
            "[": TT.LBRACKET, "]": TT.RBRACKET,
            "{": TT.LBRACE, "}": TT.RBRACE,
            "<": TT.LANGLE, ">": TT.RANGLE,
            ":": TT.COLON, ",": TT.COMMA,
            "?": TT.QUESTION,
        }
        if ch in singles:
            tokens.append(Token(singles[ch], ch, line, col))
            i += 1
            col += 1
            continue

        # Identifier (letters, digits, underscores, dots)
        if ch.isalpha() or ch == "_":
            start_col = col
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] in "_."):
                i += 1
                col += 1
            tokens.append(Token(TT.IDENT, source[start:i], line, start_col))
            continue

        # Digits starting an identifier-like token (e.g. in version after v)
        if ch.isdigit():
            start_col = col
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] in "_."):
                i += 1
                col += 1
            tokens.append(Token(TT.IDENT, source[start:i], line, start_col))
            continue

        raise LexError(f"unexpected character: {ch!r}", line, col)

    tokens.append(Token(TT.EOF, "", line, col))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"line {line}, col {col}: {message}")
        self.line = line
        self.col = col


class _Parser:
    """Recursive-descent parser for .forma files (S-expression syntax)."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

        # IR accumulators
        self.namespace: str | None = None
        self.meta: dict[str, str] = {}
        self.shapes: dict[str, dict] = {}
        self.choices: dict[str, dict] = {}
        self.mixins: dict[str, dict] = {}

    # -- token access -------------------------------------------------------

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, token_type: str, value: str | None = None) -> Token:
        tok = self._peek()
        if tok.type != token_type:
            expected = f"{token_type}" + (f" {value!r}" if value else "")
            raise ParseError(
                f"expected {expected}, got {tok.type} {tok.value!r}",
                tok.line, tok.col,
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"expected {value!r}, got {tok.value!r}",
                tok.line, tok.col,
            )
        return self._advance()

    def _match(self, token_type: str, value: str | None = None) -> Token | None:
        tok = self._peek()
        if tok.type != token_type:
            return None
        if value is not None and tok.value != value:
            return None
        return self._advance()

    # -- top-level ----------------------------------------------------------

    def parse(self) -> dict[str, Any]:
        """Parse the entire file and return the IR dict."""
        while self._peek().type != TT.EOF:
            tok = self._peek()

            if tok.type == TT.LPAREN:
                self._parse_form()
            else:
                raise ParseError(
                    f"expected '(' to start a form, got {tok.type} {tok.value!r}",
                    tok.line, tok.col,
                )

        # Build IR dict
        ir: dict[str, Any] = {}
        if self.namespace is not None:
            self.meta["namespace"] = self.namespace
        if self.meta:
            ir["meta"] = self.meta
        if self.shapes:
            ir["shapes"] = self.shapes
        if self.choices:
            ir["choices"] = self.choices
        if self.mixins:
            ir["mixins"] = self.mixins
        return ir

    def _parse_form(self):
        """Parse a top-level form: (keyword ...)"""
        self._expect(TT.LPAREN)
        tok = self._peek()

        if tok.type != TT.IDENT:
            raise ParseError(
                f"expected keyword after '(', got {tok.type} {tok.value!r}",
                tok.line, tok.col,
            )

        keyword = tok.value
        if keyword == "namespace":
            self._parse_namespace()
        elif keyword == "model":
            self._parse_model()
        elif keyword == "mixin":
            self._parse_mixin()
        elif keyword == "mixins":
            self._parse_mixins()
        elif keyword == "choice":
            self._parse_choice()
        elif keyword == "choices":
            self._parse_choices()
        elif keyword == "shape":
            self._parse_shape()
        elif keyword == "shapes":
            self._parse_shapes()
        else:
            raise ParseError(
                f"unexpected keyword {keyword!r}",
                tok.line, tok.col,
            )
        self._expect(TT.RPAREN)

    # -- namespace ----------------------------------------------------------

    def _parse_namespace(self):
        """(namespace com.example.foo)"""
        self._expect(TT.IDENT, "namespace")
        ns_tok = self._expect(TT.IDENT)
        if self.namespace is not None:
            raise ParseError("duplicate namespace declaration", ns_tok.line, ns_tok.col)
        self.namespace = ns_tok.value

    # -- model --------------------------------------------------------------

    def _parse_model(self):
        """(model Name v8.0 "description")"""
        self._expect(TT.IDENT, "model")
        name_tok = self._expect(TT.IDENT)
        self.meta["name"] = name_tok.value

        # Version: expect an identifier like v8.0
        ver_tok = self._expect(TT.IDENT)
        ver = ver_tok.value
        if ver.startswith("v"):
            ver = ver[1:]
        self.meta["version"] = ver

        # Optional description string
        if self._peek().type == TT.STRING:
            desc_tok = self._advance()
            self.meta["description"] = desc_tok.value

    # -- mixin --------------------------------------------------------------

    def _parse_type_params(self) -> list[str]:
        """Parse optional type parameter declaration: <T, U, ...>
        Returns list of param names (empty if no angle brackets)."""
        params: list[str] = []
        if self._match(TT.LANGLE):
            params.append(self._expect(TT.IDENT).value)
            while self._match(TT.COMMA):
                params.append(self._expect(TT.IDENT).value)
            self._expect(TT.RANGLE)
        return params

    def _parse_mixin_ref(self) -> str:
        """Parse a mixin reference: Name or Name<Type, ...>"""
        name = self._expect(TT.IDENT).value
        if self._match(TT.LANGLE):
            args = [self._parse_type_expr()]
            while self._match(TT.COMMA):
                args.append(self._parse_type_expr())
            self._expect(TT.RANGLE)
            return f"{name}<{', '.join(args)}>"
        return name

    def _parse_use_list(self) -> list[str]:
        """Parse optional mixin use list: [MixinRef ...]"""
        use_list: list[str] = []
        if self._match(TT.LBRACKET):
            while self._peek().type == TT.IDENT:
                use_list.append(self._parse_mixin_ref())
            self._expect(TT.RBRACKET)
        return use_list

    def _parse_mixin_body(self):
        """Parse a single mixin: Name [<T, U>] [MixinRef ...] field ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)
        type_params = self._parse_type_params()
        use_list = self._parse_use_list()
        fields = self._parse_fields_until_rparen()
        mixin_body: dict[str, Any] = {}
        if type_params:
            mixin_body["type_params"] = type_params
        if use_list:
            mixin_body["use"] = use_list
        mixin_body["fields"] = fields
        self.mixins[name_tok.value] = mixin_body

    def _parse_mixin(self):
        """(mixin Name [<T>] [MixinRef ...] field ...)"""
        self._expect(TT.IDENT, "mixin")
        self._parse_mixin_body()

    def _parse_mixins(self):
        """(mixins (Name1 [<T>] [MixinRef ...] field ...) (Name2 field ...) ...)"""
        self._expect(TT.IDENT, "mixins")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_mixin_body()
            self._expect(TT.RPAREN)

    # -- choice -------------------------------------------------------------

    def _parse_choice_body(self):
        """Parse a single choice: Name (common ...) (Variant ...) BareVariant ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)

        choice_body: dict[str, Any] = {}
        while self._peek().type != TT.RPAREN and self._peek().type != TT.EOF:
            if self._peek().type == TT.LPAREN:
                # Sub-form: either (common ...) or (Variant ...)
                self._advance()  # consume '('
                block_name_tok = self._expect(TT.IDENT)
                fields = self._parse_fields_until_rparen()
                self._expect(TT.RPAREN)

                if block_name_tok.value == "common":
                    choice_body["common"] = fields
                else:
                    choice_body[block_name_tok.value] = fields
            elif self._peek().type == TT.IDENT:
                # Bare variant (no fields)
                variant_name = self._advance().value
                choice_body[variant_name] = {}
            else:
                tok = self._peek()
                raise ParseError(
                    f"expected variant name or '(' in choice, got {tok.type} {tok.value!r}",
                    tok.line, tok.col,
                )

        self.choices[name_tok.value] = choice_body

    def _parse_choice(self):
        """(choice Name (common ...) (Variant ...) BareVariant ...)"""
        self._expect(TT.IDENT, "choice")
        self._parse_choice_body()

    def _parse_choices(self):
        """(choices (Name1 Variant ...) (Name2 (common ...) Variant ...) ...)"""
        self._expect(TT.IDENT, "choices")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_choice_body()
            self._expect(TT.RPAREN)

    # -- shape --------------------------------------------------------------

    def _parse_shape_body(self):
        """Parse a single shape: Name [MixinRef ...] field ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)

        # Optional mixin list in brackets
        use_list = self._parse_use_list()

        fields = self._parse_fields_until_rparen()

        shape_body: dict[str, Any] = {}
        if use_list:
            shape_body["use"] = use_list
        shape_body["fields"] = fields
        self.shapes[name_tok.value] = shape_body

    def _parse_shape(self):
        """(shape Name [Mixin1<T> Mixin2] field ...)"""
        self._expect(TT.IDENT, "shape")
        self._parse_shape_body()

    def _parse_shapes(self):
        """(shapes (Name1 [Mixin] field ...) (Name2 field ...) ...)"""
        self._expect(TT.IDENT, "shapes")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_shape_body()
            self._expect(TT.RPAREN)

    # -- fields -------------------------------------------------------------

    def _parse_fields_until_rparen(self) -> dict[str, str]:
        """Parse fields until we see ')'. Does NOT consume the ')'."""
        fields: dict[str, str] = {}
        while self._peek().type == TT.IDENT:
            # Lookahead: if this IDENT is followed by ':', it's a field.
            # Otherwise it might be a bare variant name or enum value.
            name_tok = self._advance()

            if self._peek().type != TT.COLON:
                # Not a field — put the token back
                self.pos -= 1
                break

            self._expect(TT.COLON)
            type_str = self._parse_type_expr()
            fields[name_tok.value] = type_str
        return fields

    def _parse_type_expr(self) -> str:
        """Parse a type expression like '[Observation]?' or '{string, json}' or 'tree<T>'"""
        tok = self._peek()

        # Anonymous collection: [T, ...]
        if tok.type == TT.LBRACKET:
            self._advance()
            args = [self._parse_type_expr()]
            while self._match(TT.COMMA):
                args.append(self._parse_type_expr())
            self._expect(TT.RBRACKET)
            base = f"[{', '.join(args)}]"
            if self._match(TT.QUESTION):
                base += "?"
            return base

        # Anonymous association: {K, V}
        if tok.type == TT.LBRACE:
            self._advance()
            key_type = self._parse_type_expr()
            self._expect(TT.COMMA)
            val_type = self._parse_type_expr()
            self._expect(TT.RBRACE)
            base = f"{{{key_type}, {val_type}}}"
            if self._match(TT.QUESTION):
                base += "?"
            return base

        # Named type, possibly with generic args: IDENT or IDENT<T, ...>
        base = self._expect(TT.IDENT).value
        if self._match(TT.LANGLE):
            args = [self._parse_type_expr()]
            while self._match(TT.COMMA):
                args.append(self._parse_type_expr())
            self._expect(TT.RANGLE)
            base = f"{base}<{', '.join(args)}>"

        if self._match(TT.QUESTION):
            base += "?"

        return base

    # -- mixin field expansion (for IR compatibility) -----------------------

    def _expand_mixins(self, ir: dict) -> dict:
        """No-op: mixin expansion is handled by the validator/downstream.
        The IR just records the `use:` list and `mixins:` definitions."""
        return ir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_forma(source: str) -> dict[str, Any]:
    """Parse a .forma source string and return an IR dict.

    The returned dict has keys: meta, shapes, choices, mixins.

    Raises ParseError or LexError on malformed input.
    """
    tokens = _lex(source)
    parser = _Parser(tokens)
    return parser.parse()


def parse_forma_file(path: str | Path) -> dict[str, Any]:
    """Parse a .forma file and return an IR dict."""
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    return parse_forma(source)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point: parse a .forma file and print the IR as YAML."""
    if len(sys.argv) != 2:
        print("Usage: python forma_parser.py <file.forma>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    try:
        ir = parse_forma_file(path)
    except (LexError, ParseError) as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print as YAML if available, otherwise JSON
    try:
        import yaml
        print(yaml.dump(ir, default_flow_style=False, sort_keys=False))
    except ImportError:
        import json
        print(json.dumps(ir, indent=2))


if __name__ == "__main__":
    main()
