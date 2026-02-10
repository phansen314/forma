#!/usr/bin/env python3
"""Forma DSL parser (S-expression syntax).

Parses .forma files into an IR dict that the ModelValidator can validate.

Grammar (EBNF):

    file           = { comment | form } EOF
    form           = "(" ( model_form | alias_form | aliases_form
                         | mixin_form | mixins_form
                         | enum_form | enums_form
                         | type_form | types_form
                         | union_form | unions_form ) ")"

    model_form     = "model" IDENT version [ STRING ]
    version        = IDENT                          // e.g. v7.0
    alias_form     = "alias" IDENT IDENT
    aliases_form   = "aliases" { IDENT IDENT }
    mixin_form     = "mixin" IDENT [ "<" IDENT { "," IDENT } ">" ] { field }
    mixins_form    = "mixins" { "(" IDENT [ "<" IDENT { "," IDENT } ">" ] { field } ")" }
    enum_form      = "enum" IDENT { IDENT }
    enums_form     = "enums" { "(" IDENT { IDENT } ")" }
    type_form      = "type" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field }
    types_form     = "types" { "(" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field } ")" }
    union_form     = "union" IDENT { common_form | variant }
    unions_form    = "unions" { "(" IDENT { common_form | variant } ")" }
    common_form    = "(" "common" { field } ")"
    variant        = IDENT | "(" IDENT { field } ")"

    mixin_ref      = IDENT [ "<" type_expr { "," type_expr } ">" ]
    field          = IDENT ":" type_expr
    type_expr      = base_type [ "?" ]
    base_type      = IDENT [ "<" type_expr { "," type_expr } ">" ]
                   | "[" type_expr { "," type_expr } "]"
                   | "{" type_expr "," type_expr "}"

    comment        = "//" ... EOL
    STRING         = '"' ... '"'
    IDENT          = letter { letter | digit | "_" | "." }

Usage:
    from forma_parser import parse_forma

    ir = parse_forma(source_text)
    # ir is a dict with keys: meta, types, unions, enums, type_aliases, mixins
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

        # Line comment
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
            # Skip to end of line
            while i < len(source) and source[i] != "\n":
                i += 1
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
        self.meta: dict[str, str] = {}
        self.types: dict[str, dict] = {}
        self.unions: dict[str, dict] = {}
        self.enums: dict[str, list[str]] = {}
        self.type_aliases: dict[str, str] = {}
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
        if self.meta:
            ir["meta"] = self.meta
        if self.types:
            ir["types"] = self.types
        if self.unions:
            ir["unions"] = self.unions
        if self.enums:
            ir["enums"] = self.enums
        if self.type_aliases:
            ir["type_aliases"] = self.type_aliases
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
        if keyword == "model":
            self._parse_model()
        elif keyword == "alias":
            self._parse_alias()
        elif keyword == "aliases":
            self._parse_aliases()
        elif keyword == "mixin":
            self._parse_mixin()
        elif keyword == "mixins":
            self._parse_mixins()
        elif keyword == "enum":
            self._parse_enum()
        elif keyword == "enums":
            self._parse_enums()
        elif keyword == "type":
            self._parse_type()
        elif keyword == "types":
            self._parse_types()
        elif keyword == "union":
            self._parse_union()
        elif keyword == "unions":
            self._parse_unions()
        else:
            raise ParseError(
                f"unexpected keyword {keyword!r}",
                tok.line, tok.col,
            )
        self._expect(TT.RPAREN)

    # -- model --------------------------------------------------------------

    def _parse_model(self):
        """(model Name v7.0 "description")"""
        self._expect(TT.IDENT, "model")
        name_tok = self._expect(TT.IDENT)
        self.meta["name"] = name_tok.value

        # Version: expect an identifier like v7.0
        ver_tok = self._expect(TT.IDENT)
        ver = ver_tok.value
        if ver.startswith("v"):
            ver = ver[1:]
        self.meta["version"] = ver

        # Optional description string
        if self._peek().type == TT.STRING:
            desc_tok = self._advance()
            self.meta["description"] = desc_tok.value

    # -- alias --------------------------------------------------------------

    def _parse_alias_body(self):
        """Parse a single alias: Name Target (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)
        target_tok = self._expect(TT.IDENT)
        self.type_aliases[name_tok.value] = target_tok.value

    def _parse_alias(self):
        """(alias Name Target)"""
        self._expect(TT.IDENT, "alias")
        self._parse_alias_body()

    def _parse_aliases(self):
        """(aliases Name1 Target1 Name2 Target2 ...)"""
        self._expect(TT.IDENT, "aliases")
        while self._peek().type == TT.IDENT:
            self._parse_alias_body()

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

    def _parse_mixin_body(self):
        """Parse a single mixin: Name [<T, U>] field ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)
        type_params = self._parse_type_params()
        fields = self._parse_fields_until_rparen()
        mixin_body: dict[str, Any] = {}
        if type_params:
            mixin_body["type_params"] = type_params
        mixin_body["fields"] = fields
        self.mixins[name_tok.value] = mixin_body

    def _parse_mixin(self):
        """(mixin Name [<T>] field ...)"""
        self._expect(TT.IDENT, "mixin")
        self._parse_mixin_body()

    def _parse_mixins(self):
        """(mixins (Name1 [<T>] field ...) (Name2 field ...) ...)"""
        self._expect(TT.IDENT, "mixins")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_mixin_body()
            self._expect(TT.RPAREN)

    # -- enum ---------------------------------------------------------------

    def _parse_enum_body(self):
        """Parse a single enum: Name val1 val2 ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)
        values = []
        while self._peek().type == TT.IDENT:
            values.append(self._advance().value)
        self.enums[name_tok.value] = values

    def _parse_enum(self):
        """(enum Name val1 val2 ...)"""
        self._expect(TT.IDENT, "enum")
        self._parse_enum_body()

    def _parse_enums(self):
        """(enums (Name1 val ...) (Name2 val ...) ...)"""
        self._expect(TT.IDENT, "enums")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_enum_body()
            self._expect(TT.RPAREN)

    # -- type ---------------------------------------------------------------

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

    def _parse_type_body(self):
        """Parse a single type: Name [MixinRef ...] field ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)

        # Optional mixin list in brackets
        use_list: list[str] = []
        if self._match(TT.LBRACKET):
            while self._peek().type == TT.IDENT:
                use_list.append(self._parse_mixin_ref())
            self._expect(TT.RBRACKET)

        fields = self._parse_fields_until_rparen()

        type_body: dict[str, Any] = {}
        if use_list:
            type_body["use"] = use_list
        type_body["fields"] = fields
        self.types[name_tok.value] = type_body

    def _parse_type(self):
        """(type Name [Mixin1<T> Mixin2] field ...)"""
        self._expect(TT.IDENT, "type")
        self._parse_type_body()

    def _parse_types(self):
        """(types (Name1 [Mixin] field ...) (Name2 field ...) ...)"""
        self._expect(TT.IDENT, "types")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_type_body()
            self._expect(TT.RPAREN)

    # -- union --------------------------------------------------------------

    def _parse_union_body(self):
        """Parse a single union: Name (common ...) (Variant ...) BareVariant ... (after keyword consumed)."""
        name_tok = self._expect(TT.IDENT)

        union_body: dict[str, Any] = {}
        while self._peek().type != TT.RPAREN and self._peek().type != TT.EOF:
            if self._peek().type == TT.LPAREN:
                # Sub-form: either (common ...) or (Variant ...)
                self._advance()  # consume '('
                block_name_tok = self._expect(TT.IDENT)
                fields = self._parse_fields_until_rparen()
                self._expect(TT.RPAREN)

                if block_name_tok.value == "common":
                    union_body["common"] = fields
                else:
                    union_body[block_name_tok.value] = fields
            elif self._peek().type == TT.IDENT:
                # Bare variant (no fields)
                variant_name = self._advance().value
                union_body[variant_name] = {}
            else:
                tok = self._peek()
                raise ParseError(
                    f"expected variant name or '(' in union, got {tok.type} {tok.value!r}",
                    tok.line, tok.col,
                )

        self.unions[name_tok.value] = union_body

    def _parse_union(self):
        """(union Name (common ...) (Variant ...) BareVariant ...)"""
        self._expect(TT.IDENT, "union")
        self._parse_union_body()

    def _parse_unions(self):
        """(unions (Name1 Variant ...) (Name2 (common ...) Variant ...) ...)"""
        self._expect(TT.IDENT, "unions")
        while self._peek().type == TT.LPAREN:
            self._advance()  # consume '('
            self._parse_union_body()
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

    The returned dict has keys: meta, types, unions, enums, type_aliases, mixins.

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
