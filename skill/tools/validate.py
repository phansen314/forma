#!/usr/bin/env python3
"""Forma hub model validator.

Validates a Forma hub model (.forma) against the spec:
  - Valid structure (.forma DSL)
  - Required sections and fields
  - Type references resolve (shapes, choices, or atoms)
  - Generic mixin arity and type substitution
  - Mixin composition (transitive expansion, cycle detection)

Usage:
    python skill/tools/validate.py <model.forma>

Exit codes:
    0  Valid (warnings are OK)
    1  Errors found
    2  Bad usage / file not found
"""

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TOP_LEVEL_KEYS = frozenset([
    "meta", "shapes", "choices", "mixins",
])

VALID_SHAPE_SUB_KEYS = frozenset(["use", "fields"])

VALID_MIXIN_SUB_KEYS = frozenset(["type_params", "use", "fields"])

# Regex: named wrapper — name<args>
_WRAPPER_RE = re.compile(r"^(\w+)<(.+)>$")


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

class Diagnostic:
    """A single error or warning."""

    __slots__ = ("code", "level", "message", "location")

    def __init__(self, code: str, level: str, message: str, location: str):
        self.code = code
        self.level = level  # "error" or "warning"
        self.message = message
        self.location = location

    def __str__(self):
        return f"{self.level}[{self.code}]: {self.message}\n  --> {self.location}"


# ---------------------------------------------------------------------------
# ModelValidator
# ---------------------------------------------------------------------------

class ModelValidator:
    """Validates a parsed Forma hub model dict."""

    def __init__(self, data: dict):
        self.data = data
        self.errors: list[Diagnostic] = []
        self.warnings: list[Diagnostic] = []

        # Type registry — populated by _build_type_registry
        self.shapes: set[str] = set()
        self.choices: set[str] = set()
        self.mixins: set[str] = set()

        # Mixin field maps (mixin_name → {field_name: type_str})
        self.mixin_fields: dict[str, dict] = {}

        # Mixin type params (mixin_name → [param_names])
        self.mixin_type_params: dict[str, list[str]] = {}

        # Mixin composition (mixin_name → [mixin_ref_strings])
        self.mixin_use: dict[str, list[str]] = {}

    # -- public API ---------------------------------------------------------

    def validate(self) -> tuple[list[Diagnostic], list[Diagnostic]]:
        """Run all validation passes. Returns (errors, warnings)."""
        self._build_type_registry()
        self._check_duplicate_type_names()
        self._validate_top_level_keys()
        self._validate_meta()
        self._validate_mixins()
        self._validate_choices()
        self._validate_shapes()
        return self.errors, self.warnings

    # -- helpers ------------------------------------------------------------

    def _error(self, code: str, message: str, location: str):
        self.errors.append(Diagnostic(code, "error", message, location))

    def _warn(self, code: str, message: str, location: str):
        self.warnings.append(Diagnostic(code, "warning", message, location))

    def _all_type_names(self) -> set[str]:
        return self.shapes | self.choices | self.mixins

    # -- type resolution ----------------------------------------------------

    def _resolve_type(self, raw: str, location: str) -> bool:
        """Validate a type string. Returns True if valid, False otherwise.

        Handles:
          - Simple types: `string`, `Bird`
          - Anonymous collections: `[T]`, `[T, U]`
          - Anonymous associations: `{K, V}`
          - Named wrappers: `tree<T>`
          - Nullable suffix: any of the above followed by `?`

        Unknown names are valid atoms — no warnings emitted.
        Emits errors/warnings as side effects.
        """
        if not isinstance(raw, str):
            self._error("E041", f"field type is not a string: {raw!r}", location)
            return False

        # Strip nullable suffix
        type_str = raw.rstrip("?")
        if not type_str:
            self._error("E041", "empty type string", location)
            return False

        # Anonymous collection: [T] or [T, U]
        if type_str.startswith("[") and type_str.endswith("]"):
            inner = type_str[1:-1]
            args = _split_type_args(inner)
            for arg in args:
                arg = arg.strip()
                if arg.endswith("?"):
                    self._warn("W019", f"nullable element type \"{arg}\" inside collection — nullable collection elements are discouraged", location)
                self._resolve_type(arg, location)
            return True

        # Anonymous association: {K, V}
        if type_str.startswith("{") and type_str.endswith("}"):
            inner = type_str[1:-1]
            args = _split_type_args(inner)
            if len(args) != 2:
                self._error("E041", f"association {{K, V}} requires exactly 2 type arguments, got {len(args)}", location)
                return False
            for arg in args:
                self._resolve_type(arg.strip(), location)
            return True

        # Named wrapper: name<args>
        m = _WRAPPER_RE.match(type_str)
        if m:
            wrapper_name = m.group(1)
            args_str = m.group(2)
            self._warn("W015", f"named wrapper \"{wrapper_name}\"", location)
            args = _split_type_args(args_str)
            for arg in args:
                arg = arg.strip()
                if arg.endswith("?"):
                    self._warn("W019", f"nullable element type \"{arg}\" inside wrapper \"{wrapper_name}\" — nullable collection elements are discouraged", location)
                self._resolve_type(arg, location)
            return True

        # Check user-defined shapes and choices
        if type_str in self.shapes or type_str in self.choices:
            return True

        # Mixin used as field type
        if type_str in self.mixins:
            self._error("E042", f"mixin \"{type_str}\" cannot be used as a field type (use a shape instead)", location)
            return False

        # Atom — any unresolved name is valid
        return True

    # -- registry -----------------------------------------------------------

    def _build_type_registry(self):
        """Collect all declared type names from each section."""
        data = self.data

        for name in _section_keys(data, "shapes"):
            self.shapes.add(name)

        for name in _section_keys(data, "choices"):
            self.choices.add(name)

        for name in _section_keys(data, "mixins"):
            self.mixins.add(name)
            section = data["mixins"][name]
            if isinstance(section, dict):
                fields = section.get("fields")
                if isinstance(fields, dict):
                    self.mixin_fields[name] = fields
                    type_params = section.get("type_params")
                    if isinstance(type_params, list):
                        self.mixin_type_params[name] = type_params
                    use_list = section.get("use")
                    if isinstance(use_list, list):
                        self.mixin_use[name] = use_list

    # -- duplicate / collision checks ---------------------------------------

    def _check_duplicate_type_names(self):
        """E100: same name in two type-defining sections."""
        seen: dict[str, str] = {}  # name → section
        sections = [
            ("shapes", self.shapes),
            ("choices", self.choices),
        ]
        for section_name, names in sections:
            for name in names:
                if name in seen:
                    self._error("E100", f"\"{name}\" is defined in both \"{seen[name]}\" and \"{section_name}\"", f"{section_name}.{name}")
                else:
                    seen[name] = section_name

        # Mixins are not types, but still shouldn't collide with other names
        for name in self.mixins:
            if name in seen:
                self._error("E100", f"\"{name}\" is defined in both \"{seen[name]}\" and \"mixins\"", f"mixins.{name}")
            else:
                seen[name] = "mixins"

    # -- top-level keys -----------------------------------------------------

    def _validate_top_level_keys(self):
        if not isinstance(self.data, dict):
            return
        for key in self.data:
            if key not in VALID_TOP_LEVEL_KEYS:
                self._error("E010", f"unknown top-level key \"{key}\"", key)

    # -- meta ---------------------------------------------------------------

    def _validate_meta(self):
        meta = self.data.get("meta")
        if meta is None:
            self._error("E001", "\"meta\" section is missing", "meta")
            return
        if not isinstance(meta, dict):
            self._error("E011", "\"meta\" must be a mapping", "meta")
            return

        if "name" not in meta or not isinstance(meta.get("name"), str):
            self._error("E002", "\"meta.name\" is missing or not a string", "meta.name")
        if "version" not in meta or not isinstance(meta.get("version"), str):
            self._error("E003", "\"meta.version\" is missing or not a string", "meta.version")
        if "description" not in meta:
            self._warn("W013", "\"meta.description\" is missing", "meta")

        # Optional namespace — validate type if present
        ns = meta.get("namespace")
        if ns is not None and (not isinstance(ns, str) or len(ns) == 0):
            self._error("E004", "\"meta.namespace\" must be a non-empty string", "meta.namespace")

    # -- choices ------------------------------------------------------------

    def _validate_choices(self):
        section = self.data.get("choices")
        if section is None:
            return
        if not isinstance(section, dict):
            self._error("E011", "\"choices\" must be a mapping", "choices")
            return
        if len(section) == 0:
            self._warn("W017", "\"choices\" section is empty", "choices")
            return

        for name, body in section.items():
            loc = f"choices.{name}"

            if not isinstance(body, dict):
                self._error("E011", f"choice \"{name}\" must be a mapping", loc)
                continue

            # Separate common from variants
            common = body.get("common")
            if common is not None and not isinstance(common, dict):
                self._error("E053", f"\"common\" block in choice \"{name}\" must be a mapping", f"{loc}.common")

            variants = {k: v for k, v in body.items() if k != "common"}
            if len(variants) < 2:
                self._error("E050", f"choice \"{name}\" must have at least 2 variants (has {len(variants)})", loc)

            # Validate common fields
            if isinstance(common, dict):
                for field_name, field_type in common.items():
                    field_loc = f"{loc}.common.{field_name}"
                    if isinstance(field_type, str):
                        self._resolve_type(field_type, field_loc)

            # Validate variant fields
            for vname, vfields in variants.items():
                vloc = f"{loc}.{vname}"

                if vfields is None:
                    continue
                if not isinstance(vfields, dict):
                    self._error("E051", f"variant \"{vname}\" in choice \"{name}\" must be a mapping or empty", vloc)
                    continue

                for field_name, field_type in vfields.items():
                    field_loc = f"{vloc}.{field_name}"
                    if isinstance(field_type, str):
                        self._resolve_type(field_type, field_loc)

    # -- mixins -------------------------------------------------------------

    def _validate_mixins(self):
        section = self.data.get("mixins")
        if section is None:
            return
        if not isinstance(section, dict):
            self._error("E011", "\"mixins\" must be a mapping", "mixins")
            return
        if len(section) == 0:
            self._warn("W017", "\"mixins\" section is empty", "mixins")
            return

        for name, body in section.items():
            loc = f"mixins.{name}"

            if not isinstance(body, dict):
                self._error("E060", f"mixin \"{name}\" must have fields (got {type(body).__name__})", loc)
                continue

            # Check sub-keys
            for key in body:
                if key not in VALID_MIXIN_SUB_KEYS:
                    self._error("E060", f"unknown key \"{key}\" in mixin \"{name}\"", f"{loc}.{key}")

            fields = body.get("fields")
            if not isinstance(fields, dict):
                self._error("E060", f"mixin \"{name}\" must have fields", loc)
                continue
            if len(fields) == 0:
                self._error("E060", f"mixin \"{name}\" has no fields", loc)
                continue

            # Validate type_params
            type_params = body.get("type_params")
            param_set: set[str] = set()
            if type_params is not None:
                if not isinstance(type_params, list):
                    self._error("E065", f"\"type_params\" in mixin \"{name}\" must be a list", f"{loc}.type_params")
                else:
                    for p in type_params:
                        if not isinstance(p, str):
                            self._error("E065", f"type parameter must be a string, got {type(p).__name__}", f"{loc}.type_params")
                        else:
                            param_set.add(p)

            # Validate use list (mixin composition)
            use_list = body.get("use")
            if use_list is not None:
                if not isinstance(use_list, list):
                    self._error("E092", f"\"use\" in mixin \"{name}\" must be a list", f"{loc}.use")
                else:
                    for mixin_ref in use_list:
                        mixin_str = str(mixin_ref)
                        mixin_name, type_args = self._parse_mixin_ref(mixin_str)
                        if mixin_name not in self.mixins:
                            self._error("E092", f"mixin \"{name}\" references unknown mixin \"{mixin_name}\"", f"{loc}.use")

            # Check for circular composition
            if self._detect_mixin_cycle(name, set(), []):
                pass  # error already emitted by _detect_mixin_cycle

            for field_name, field_type in fields.items():
                field_loc = f"{loc}.{field_name}"
                if isinstance(field_type, str):
                    # Skip resolution for type parameter names
                    if not self._type_uses_only_params(field_type, param_set):
                        self._resolve_type(field_type, field_loc)

    def _detect_mixin_cycle(self, name: str, visiting: set[str], path: list[str]) -> bool:
        """Detect circular mixin composition. Returns True if cycle found."""
        if name in visiting:
            cycle_path = " -> ".join(path + [name])
            self._error("E091", f"circular mixin composition: {cycle_path}", f"mixins.{name}")
            return True
        if name not in self.mixin_use:
            return False
        visiting = visiting | {name}
        for ref_str in self.mixin_use[name]:
            ref_name, _ = self._parse_mixin_ref(ref_str)
            if self._detect_mixin_cycle(ref_name, visiting, path + [name]):
                return True
        return False

    def _type_uses_only_params(self, type_str: str, params: set[str]) -> bool:
        """Check if a type string contains type parameters that should skip resolution.
        Returns True if the base type is a parameter (meaning we skip full resolution)."""
        stripped = type_str.rstrip("?")
        if not stripped:
            return False
        # Simple param reference: T, T?
        if stripped in params:
            return True
        # Collection of param: [T]
        if stripped.startswith("[") and stripped.endswith("]"):
            inner = stripped[1:-1]
            args = _split_type_args(inner)
            return all(self._type_uses_only_params(a.strip(), params) for a in args)
        # Association of params: {T, U}
        if stripped.startswith("{") and stripped.endswith("}"):
            inner = stripped[1:-1]
            args = _split_type_args(inner)
            return all(self._type_uses_only_params(a.strip(), params) for a in args)
        # Wrapper with params: tree<T>
        m = _WRAPPER_RE.match(stripped)
        if m:
            args_str = m.group(2)
            args = _split_type_args(args_str)
            return all(self._type_uses_only_params(a.strip(), params) for a in args)
        return False

    # -- shapes -------------------------------------------------------------

    def _parse_mixin_ref(self, ref_str: str) -> tuple[str, list[str]]:
        """Parse a mixin reference string like 'Versioned<Bird>' into (name, [args]).
        Returns (name, []) for plain refs like 'Timestamped'."""
        m = _WRAPPER_RE.match(ref_str)
        if m:
            name = m.group(1)
            args_str = m.group(2)
            args = [a.strip() for a in _split_type_args(args_str)]
            return name, args
        return ref_str, []

    def _resolve_mixin_fields(self, mixin_name: str, type_args: list[str], loc: str, visited: set[str] | None = None) -> dict[str, str]:
        """Resolve mixin fields by substituting type parameters with concrete types.
        Handles transitive composition via 'use' lists.
        Returns the resolved field map."""
        if visited is None:
            visited = set()
        if mixin_name in visited:
            return {}  # cycle — already reported by _detect_mixin_cycle
        visited = visited | {mixin_name}

        fields = self.mixin_fields.get(mixin_name, {})
        params = self.mixin_type_params.get(mixin_name, [])

        # Start with composed mixin fields
        all_fields: dict[str, str] = {}

        # Expand composed mixins first
        use_list = self.mixin_use.get(mixin_name, [])
        for ref_str in use_list:
            ref_name, ref_args = self._parse_mixin_ref(ref_str)
            if ref_name in self.mixin_fields:
                composed_fields = self._resolve_mixin_fields(ref_name, ref_args, loc, visited)
                all_fields.update(composed_fields)

        # Build substitution map from own type params
        subst: dict[str, str] = {}
        if params:
            for i, param in enumerate(params):
                if i < len(type_args):
                    subst[param] = type_args[i]

        # Add own fields (with substitution)
        for fname, ftype in fields.items():
            if subst:
                all_fields[fname] = _substitute_type_params(ftype, subst)
            else:
                all_fields[fname] = ftype

        return all_fields

    def _validate_shapes(self):
        section = self.data.get("shapes")
        if section is None:
            return
        if not isinstance(section, dict):
            self._error("E011", "\"shapes\" must be a mapping", "shapes")
            return
        if len(section) == 0:
            self._warn("W017", "\"shapes\" section is empty", "shapes")
            return

        for name, body in section.items():
            loc = f"shapes.{name}"

            if not isinstance(body, dict):
                self._error("E011", f"shape \"{name}\" must be a mapping", loc)
                continue

            # Check sub-keys
            for key in body:
                if key not in VALID_SHAPE_SUB_KEYS:
                    self._error("E085", f"unknown key \"{key}\" in shape \"{name}\"", f"{loc}.{key}")

            # Validate use (mixins)
            use_list = body.get("use")
            resolved_mixin_fields: dict[str, str] = {}  # field_name → source_mixin
            if use_list is not None:
                if not isinstance(use_list, list):
                    self._error("E083", f"\"use\" in shape \"{name}\" must be a list", f"{loc}.use")
                else:
                    for mixin_ref in use_list:
                        mixin_str = str(mixin_ref)
                        mixin_name, type_args = self._parse_mixin_ref(mixin_str)

                        if mixin_name not in self.mixins:
                            self._error("E084", f"unknown mixin \"{mixin_name}\" in shape \"{name}\"", f"{loc}.use")
                        else:
                            # Stage 1: check arity
                            expected_params = self.mixin_type_params.get(mixin_name, [])
                            if len(type_args) != len(expected_params):
                                if len(expected_params) == 0 and len(type_args) == 0:
                                    pass  # non-generic mixin, no args — fine
                                elif len(expected_params) > 0 and len(type_args) == 0:
                                    self._error("E086", f"mixin \"{mixin_name}\" requires {len(expected_params)} type argument(s), got 0", f"{loc}.use")
                                elif len(expected_params) == 0 and len(type_args) > 0:
                                    self._error("E086", f"mixin \"{mixin_name}\" is not generic but got {len(type_args)} type argument(s)", f"{loc}.use")
                                else:
                                    self._error("E086", f"mixin \"{mixin_name}\" requires {len(expected_params)} type argument(s), got {len(type_args)}", f"{loc}.use")

                            # Validate type arguments resolve
                            for arg in type_args:
                                self._resolve_type(arg, f"{loc}.use")

                            # Stage 2: resolve fields with substitution (including composition)
                            if mixin_name in self.mixin_fields:
                                resolved_fields = self._resolve_mixin_fields(mixin_name, type_args, f"{loc}.use")
                                for mf_name, mf_type in resolved_fields.items():
                                    if mf_name in resolved_mixin_fields:
                                        self._error("E090", f"field \"{mf_name}\" is defined in both mixin \"{resolved_mixin_fields[mf_name]}\" and mixin \"{mixin_name}\"", f"{loc}.use")
                                    else:
                                        resolved_mixin_fields[mf_name] = mixin_name
                                        # Validate the resolved field type
                                        self._resolve_type(mf_type, f"{loc}.use.{mixin_name}.{mf_name}")

            # Validate fields
            fields = body.get("fields")
            if fields is None:
                self._error("E070", f"shape \"{name}\" is missing \"fields\" section", loc)
            elif not isinstance(fields, dict):
                self._error("E011", f"\"fields\" in shape \"{name}\" must be a mapping", f"{loc}.fields")
            else:
                if len(fields) == 0:
                    self._error("E070", f"shape \"{name}\" has no fields", f"{loc}.fields")

                for field_name, field_type in fields.items():
                    field_loc = f"{loc}.fields.{field_name}"

                    # Check mixin field conflict
                    if str(field_name) in resolved_mixin_fields:
                        self._warn("W012", f"field \"{field_name}\" in shape \"{name}\" shadows mixin field from \"{resolved_mixin_fields[str(field_name)]}\"", field_loc)

                    # Validate field type
                    if not isinstance(field_type, str):
                        self._error("E075", f"field type must be a string, got {type(field_type).__name__} ({field_type!r})", field_loc)
                    else:
                        self._resolve_type(field_type, field_loc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_type_args(s: str) -> list[str]:
    """Split a type argument string by commas, respecting nested delimiters.

    e.g. "string, json" → ["string", "json"]
         "{string, json}, int" → ["{string, json}", "int"]
         "[int], string" → ["[int]", "string"]
         "tree<Category>, int" → ["tree<Category>", "int"]
    """
    args = []
    depth = 0
    current = []
    for ch in s:
        if ch in ("[", "{", "<"):
            depth += 1
            current.append(ch)
        elif ch in ("]", "}", ">"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current).strip())
    return args


def _substitute_type_params(type_str: str, subst: dict[str, str]) -> str:
    """Substitute type parameters in a type string.

    e.g. with subst {"T": "Bird"}:
      "T" → "Bird"
      "[T]" → "[Bird]"
      "{T, int}" → "{Bird, int}"
      "tree<T>" → "tree<Bird>"
      "T?" → "Bird?"
    """
    nullable = type_str.endswith("?")
    base = type_str.rstrip("?") if nullable else type_str

    # Simple param
    if base in subst:
        result = subst[base]
        return result + "?" if nullable else result

    # Collection: [T]
    if base.startswith("[") and base.endswith("]"):
        inner = base[1:-1]
        args = _split_type_args(inner)
        resolved = ", ".join(_substitute_type_params(a.strip(), subst) for a in args)
        result = f"[{resolved}]"
        return result + "?" if nullable else result

    # Association: {K, V}
    if base.startswith("{") and base.endswith("}"):
        inner = base[1:-1]
        args = _split_type_args(inner)
        resolved = ", ".join(_substitute_type_params(a.strip(), subst) for a in args)
        result = f"{{{resolved}}}"
        return result + "?" if nullable else result

    # Named wrapper: name<args>
    m = _WRAPPER_RE.match(base)
    if m:
        wrapper_name = m.group(1)
        args_str = m.group(2)
        args = _split_type_args(args_str)
        resolved = ", ".join(_substitute_type_params(a.strip(), subst) for a in args)
        result = f"{wrapper_name}<{resolved}>"
        return result + "?" if nullable else result

    # Not a param, return as-is
    return type_str


def _section_keys(data: dict, section: str) -> list[str]:
    """Return the keys of a top-level section if it's a dict, else empty."""
    val = data.get(section)
    if isinstance(val, dict):
        return list(val.keys())
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: python skill/tools/validate.py <model.forma>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    if path.suffix != ".forma":
        print(f"Error: only .forma files are supported (got {path.suffix})", file=sys.stderr)
        sys.exit(2)

    print(f"Validating {path} ...")
    print()

    from forma_parser import parse_forma_file, LexError, ParseError
    try:
        data = parse_forma_file(path)
    except (LexError, ParseError) as e:
        print(f"error[E000]: .forma parse failure")
        print(f"  {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        print(f"error[E000]: file did not parse as a mapping")
        sys.exit(1)

    # Validate
    validator = ModelValidator(data)
    errors, warnings = validator.validate()

    # Print diagnostics
    for diag in errors + warnings:
        print(diag)
        print()

    # Summary
    n_err = len(errors)
    n_warn = len(warnings)

    if n_err == 0 and n_warn == 0:
        meta = data.get("meta", {})
        name = meta.get("name", "<unnamed>") if isinstance(meta, dict) else "<unnamed>"
        version = meta.get("version", "?") if isinstance(meta, dict) else "?"
        print(f"[OK] Model \"{name}\" v{version} is valid.")
        sys.exit(0)
    elif n_err == 0:
        meta = data.get("meta", {})
        name = meta.get("name", "<unnamed>") if isinstance(meta, dict) else "<unnamed>"
        version = meta.get("version", "?") if isinstance(meta, dict) else "?"
        print(f"[OK] Model \"{name}\" v{version} is valid ({n_warn} warning(s)).")
        sys.exit(0)
    else:
        print(f"Found {n_err} error(s) and {n_warn} warning(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
