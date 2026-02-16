# Changelog

All notable changes to Forma will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **BREAKING**: Removed base profiles (`profiles/` directory), `globals:` key, and `--no-base` flag. Model-specific satellites are self-contained. Satellite merge order simplified from 5 steps to 4: hub → convention satellite → explicit satellites → layer profiles.
- **BREAKING**: Merged `generators:` section into `emitters:` in target profile satellites. Each named emitter now contains both generation settings (package, immutability, collections, serialization, validation) and concept mapping (default styles + per-name overrides). The `generators:` top-level key is removed. Eliminates the need to look in two places for settings that are always 1:1 keyed by the same name.
- **BREAKING**: Removed `default.atom` from emitter default blocks. Domain atom base types are now declared in `emitters.atoms` instead. Atoms without per-name style overrides get transparent treatment (typealias in Kotlin, plain column type in SQL).
- **BREAKING**: Removed `default:` block from emitters. `shape:` and `choice:` are now top-level emitter keys alongside `package:`, `immutability:`, etc. — one less nesting level. No collision with per-name overrides (which use PascalCase).

### Added
- **`emitters.atoms`** — reserved sub-section within `emitters:` for explicit domain atom → base type resolution. Maps domain atoms like `BirdId`, `Email` to their base types (`UUID`, `string`), which then resolve through `type_mappings` to target-specific types. Shared across all emitters in the satellite. Two-layer resolution chain: `BirdId → emitters.atoms → UUID → type_mappings → java.util.UUID`.
- Atom coverage validation updated: an atom is covered if it appears in `type_mappings` (primitive) or `emitters.atoms` (domain). Per-name style overrides are representation directives, not coverage.
- All documentation, examples, and reference docs updated to reflect unified `emitters:` structure
- `generators.<name>.validation.context` → `emitters.<name>.validation.context`
- `generators.<name>.validation.library` → `emitters.<name>.validation.library`

### Added
- **Named validation contexts** — Validation satellites now organize rules into named contexts (`base`, `api`, `persistence`, etc.) instead of a flat structure. Each context is a self-contained rule set.
  - `extends:` — context inheritance. A child context starts with the parent's rules and overlays its own at field granularity. Unmentioned fields keep the parent's rules.
  - `default:` — per-atom-type fallback rules within a context. "All strings have `max_length: 255`" is expressed as a default. Explicit field rules always override.
  - Reserved keys within a context: `extends:` and `default:`. Everything else is a shape name.
  - Target profile interaction: `emitters.<name>.validation.context` selects which context to apply; `emitters.<name>.validation.library` controls how rules become annotations.
- **Block comments** — `/* ... */` with nesting support. `/* outer /* inner */ still outer */` is valid. Unterminated block comments are a parse error (E000). Comment delimiters are stripped during lexing (not tokens); token count stays at 12.
- **Namespace declaration** — `(namespace com.example.foo)` declares a logical package/module identity for the model. Optional, at most one per file, stored in `meta.namespace`. Generators use it as the default package when the emitter doesn't override via `package:`.
- `namespace_form` production added to EBNF grammar
- Parser: `_parse_namespace()` method, `namespace` keyword dispatch, duplicate detection
- Validator: accepts optional `namespace` key in `meta` (E004 if present but not a non-empty string)
- **CLI invocation** — `/forma <hub-file> --<target> [satellite-files...] [--validate]` provides deterministic satellite resolution. Auto-discovers convention satellites and layer profiles.
- **Atom coverage validation** — `--validate` flag checks that every atom in the hub has a resolution path (via `type_mappings` or `emitters.atoms`). Reports unmapped atoms as errors.
- Satellite merge order: hub → convention satellite → explicit satellites → layer profiles
- Documentation updated: `SPEC.md`, `SKILL.md`, `satellite-architecture.md`, `quick-reference.md`, `kotlin-profile.md`, `CLAUDE.md`

## [8.0]

### Changed
- **BREAKING**: Concept count reduced from five to three — shapes (was types), choices (unifies enums + unions), mixins (now with composition). Type aliases removed.
- **BREAKING**: `(type ...)` renamed to `(shape ...)`, `(types ...)` renamed to `(shapes ...)`
- **BREAKING**: `(enum ...)` and `(union ...)` unified into `(choice ...)`, `(enums ...)` and `(unions ...)` unified into `(choices ...)`
- **BREAKING**: `(alias ...)` and `(aliases ...)` removed — unresolved names are atoms; target profiles resolve them via `atoms:` section
- **BREAKING**: IR keys changed: `types` → `shapes`, `unions`+`enums` → `choices`, `type_aliases` removed
- **BREAKING**: Validator no longer enforces PascalCase/snake_case naming (W001, W002 warnings removed). Naming conventions are documented guidance only.
- Parser (`forma_parser.py`) rewritten: new keyword dispatch (`shape`/`shapes`/`choice`/`choices`), removed `type`/`types`/`enum`/`enums`/`union`/`unions`/`alias`/`aliases`; mixin body parsing accepts optional `[mixin_ref ...]` bracket list for composition
- Validator (`validate.py`) rewritten: registries renamed (`self.shapes`, `self.choices`), removed `_validate_enums`, `_validate_type_aliases`; added mixin composition validation with cycle detection; `_resolve_type` no longer warns on unknown names (atoms are valid)
- Satellite examples updated: `types:` → `shapes:`, `enums:`+`unions:` → `choices:`, `type_aliases:` → `atoms:`
- All documentation updated: `SPEC.md`, `SKILL.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `quick-reference.md`, `satellite-architecture.md`, `kotlin-profile.md`

### Added
- **Mixin composition** — `(mixin Auditable [Timestamped] ...)` allows mixins to include other mixins. Transitive expansion, cycle detection (E091), unknown mixin reference detection (E092).
- **Atoms** — unresolved type names are valid "atoms" that target profiles map to concrete types. Replaces type aliases without requiring hub-level declarations.
- **`choice` keyword** — unifies enums and unions. All-bare variants = enum-like, fielded variants = union-like.
- `atoms:` section in satellite profiles (replaces `type_aliases:`)
- "Changes from v7" section in spec

### Removed
- `(alias ...)` / `(aliases ...)` keywords and `type_aliases` IR key
- `(enum ...)` / `(enums ...)` keywords and `enums` IR key (use `choice` instead)
- `(type ...)` / `(types ...)` keywords (use `shape` instead)
- `(union ...)` / `(unions ...)` keywords (use `choice` instead)
- PascalCase/snake_case validation warnings (W001, W002)
- `_PASCAL_RE`, `_SNAKE_RE` constants from validator
- Alias-specific errors (E032, E020-E022)

## [7.0]

### Changed
- **BREAKING**: Named wrapper syntax changed from brackets to angle brackets — `tree[Category]` → `tree<Category>`. All type parameterization now uses `<>`.
- **BREAKING**: Token types increased from 10 to 12 — added `<` (LANGLE) and `>` (RANGLE) for generic type parameters
- Parser (`forma_parser.py`) updated: `_parse_type_expr` uses `<>` for named type params; new `_parse_type_params` and `_parse_mixin_ref` methods
- Parser mixin IR changed: mixins now emit `{"type_params": [...], "fields": {...}}` instead of flat `{field: type}` dict
- Validator (`validate.py`) updated: `_WRAPPER_RE` matches `name<args>` instead of `name[args]`; `_split_type_args` respects `<>` nesting; two-stage generic mixin validation (arity check + type substitution)
- Validator: new `VALID_MIXIN_SUB_KEYS`, `mixin_type_params`, `_substitute_type_params`, `_type_uses_only_params`, `_parse_mixin_ref`, `_resolve_mixin_fields` for generic mixin support
- All documentation updated: `SPEC.md`, `SKILL.md`, `CLAUDE.md`, `quick-reference.md`, `satellite-architecture.md`, `kotlin-profile.md`
- `[T]` and `{K, V}` reframed as shorthand sugar for `coll<T>` and `dict<K, V>` — built-in generic types

### Added
- **Generic mixins** — `(mixin Versioned<T> current: T history: [T] version: int)` declares parameterized field templates. Usage: `[Versioned<Bird>]` in type mixin list.
- `mixin_ref` production in EBNF grammar — `IDENT [ "<" type_expr { "," type_expr } ">" ]`
- New error code E086: generic mixin arity mismatch
- New error code E065: invalid `type_params` in mixin
- "Changes from v6" section in spec
- **Plural forms** — `(aliases ...)`, `(enums ...)`, `(mixins ...)`, `(types ...)`, `(unions ...)` group multiple definitions in a single S-expression. Same IR output as repeated singular forms; purely a surface-syntax convenience.
- Parser: 5 body-helper methods + 5 plural-parsing methods; dispatch updated for new keywords
- EBNF grammar updated with 5 new productions (`aliases_form`, `enums_form`, `mixins_form`, `types_form`, `unions_form`)
- "Plural Forms" section added to spec, quick reference, and CLAUDE.md
- `wingspan.forma` example converted to use plural forms

## [6.0]

### Changed
- **BREAKING**: `list[T]`, `set[T]`, `map[K, V]` replaced by structural primitives `[T]` (collection) and `{K, V}` (association) — the hub no longer implies ordering, uniqueness, or lookup behavior
- **BREAKING**: YAML hub format deprecated — `[T]` collides with YAML list syntax and `{K, V}` with flow mapping. YAML hubs still accepted with legacy `list[T]`/`set[T]`/`map[K, V]` syntax.
- Token types increased from 8 to 10 — added `{` and `}` for association syntax
- Parser (`forma_parser.py`) updated: `_parse_type_expr` handles `[T]`, `{K, V}`, and `IDENT[T]`
- Validator (`validate.py`) updated: bracket-aware type parsing replaces regex+split for nested types like `[{string, json}]`
- `BUILTIN_WRAPPERS` renamed to `LEGACY_WRAPPERS` — `list`/`set`/`map` are no longer special, just backward-compatible
- Kotlin satellite example: `list:`/`set:`/`map:` keys replaced with `collection:` and `association:` defaults
- All documentation updated: `SPEC.md`, `SKILL.md`, `CLAUDE.md`, `quick-reference.md`, `satellite-architecture.md`, `kotlin-profile.md`

### Added
- Anonymous collection syntax `[T]` — zero or more values of type T
- Anonymous association syntax `{K, V}` — key-value pairs
- `metadata: {string, json}?` field on Bird type in example (demonstrates association)
- "Changes from v5" migration table in spec
- `_split_type_args` helper in validator for bracket-aware comma splitting

## [5.0]

### Changed
- **BREAKING**: `.forma` DSL switched from C-style curly-brace syntax to S-expression syntax — every declaration is now a parenthesized form: `(keyword name ...body...)`
- **BREAKING**: Generic parameters switched from parentheses to brackets — `list(T)` → `list[T]`, `map(K, V)` → `map[K, V]`
- **BREAKING**: Mixin inheritance switched from angle bracket to bracket list — `type Foo < Mixin { ... }` → `(type Foo [Mixin] ...)`
- **BREAKING**: Enum values switched from pipe-separated to space-separated — `enum X = a | b | c` → `(enum X a b c)`
- **BREAKING**: Alias syntax switched from equals sign to juxtaposition — `alias X = Y` → `(alias X Y)`
- Token types reduced from 12 to 8 — removed `{ } = | <`
- Parser (`forma_parser.py`) rewritten for S-expression grammar
- Validator wrapper regex updated from `name(args)` to `name[args]`
- All documentation updated: `SPEC.md`, `SKILL.md`, `CLAUDE.md`, `quick-reference.md`
- W019 validator warning updated for bracket syntax (`list[string?]`, `set[Tag?]`, etc.)

### Added
- EBNF grammar for S-expression syntax in `spec/SPEC.md`
- "Changes from v4" section in spec documenting the syntax migration

## [4.0]

### Added
- **`.forma` DSL** — Custom hub syntax with minimal scaffolding. Every line in a type block is just `name: type`. Recommended for new models; YAML remains supported.
- `.forma` parser (`skill/tools/forma_parser.py`) — Recursive-descent lexer + parser producing the same IR dict as YAML
- `examples/birdtracker.forma` — Canonical BirdTracker example in `.forma` syntax
- EBNF grammar for `.forma` syntax in `spec/SPEC.md`
- Cardinality inference section in spec — targets cross-reference field types to infer 1:1, 1:N, N:M
- "What Satellites Declare" section in spec — reference table for where constraints belong

### Changed
- **BREAKING**: Constraints (`primary_key`, `unique`, `default`) moved out of the hub — they are now satellite concerns declared in target profiles or validation satellites
- **BREAKING**: Explicit `relationships:` section removed from hub types — references are plain field types (`bird: Bird`, `observations: list(Observation)`); targets infer cardinality from cross-references
- **BREAKING**: Constrained field syntax (`[type, constraint]`) removed from hub — fields are always `name: type`
- Hub is now "pure shape" — no identity, constraint, or relationship declarations
- Validator (`validate.py`) now accepts both `.forma` and `.yaml` files
- Updated all documentation: `SPEC.md`, `SKILL.md`, `CLAUDE.md`, `quick-reference.md`, `satellite-architecture.md`

## [3.0]

### Changed
- **BREAKING**: Merged `composite_types:` and `entities:` into a single `types:` section — persistence is a target concern, not a hub-level categorization
- **BREAKING**: All types now require a `fields:` sub-key (former composites had fields directly under the type name)
- **BREAKING**: Removed E043 error — any type can now be used as a field type (not just composites/unions/enums/aliases)
- Type system reduced from six concepts to five (types, unions, enums, type aliases, mixins)
- Validator: W010 "no primary_key" warning now only fires when the type has `relationships:` (value types without identity shouldn't warn)
- SQL satellite profile: added `with_primary_key` conditional default pattern for types that have a primary key
- Kotlin satellite profile: merged `composite_types:` and `entities:` sections into `types:` with `default`/`overrides`
- Updated all reference docs, examples, and skill files to use `types:` vocabulary

### Added
- Bundled model validator (`skill/tools/validate.py`) — moved from `tools/` into the skill for portability
- `examples/birdtracker.validate.yaml` — Validation satellite example for BirdTracker
- `examples/birdtracker.sql.yaml` — SQL/PostgreSQL target profile example for BirdTracker
- `CONTRIBUTING.md` — Contributor guide for adding target profiles
- `CHANGELOG.md` — This changelog
- Mermaid processing-pipeline diagram in `spec/SPEC.md`
- Mermaid hub-and-satellite diagram in `README.md`
- Type alias strategies (`type_aliases:` section) in Kotlin and SQL target profile examples

### Changed
- `README.md` — Updated repo structure to reflect new files
- `CLAUDE.md` — Updated repo structure to reflect new files

## [2.0]

### Changed
- **Entity fields**: List of single-key dicts → named map under `fields:` (direct key lookup, no duplicates, cleaner parse)
- **Nullability**: `required` constraint → `?` suffix with non-null default (less boilerplate)
- **Composite types**: Tuple string `(k: v, ...)` → YAML map (native YAML, no custom parser)
- **Foreign keys**: Manual + relationship (redundant) → derived by target profiles from relationships (single source of truth)
- **Relationships**: Mixed into field list → separate `relationships:` key at entity level
- **Meta block**: Not present → `meta:` with name/version for identity and versioning
- **Agent enrichment**: One bullet list → detailed task table + contract
- **Type/constraint mappings**: Moved from core spec to target profiles (target-specific concerns)
- **Document architecture**: Single file → hub + satellite files (keeps core small)
- **Scope**: Implicit → structure only; validation is a separate satellite concern

### Added
- `unions:` top-level block — discriminated sum types for variant data
- `enums:` top-level block — fixed value sets
- `mixins:` + `use:` — shared field templates without inheritance
- `list(T)`, `set(T)`, `map(K,V)` collection types
- `default: <value>` constraint
