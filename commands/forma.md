---
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(python *), Bash(python3 *)
argument-hint: "<hub-file> --<target> [satellites...] [--validate]"
---

# Forma — Data Model Definition Command

## Overview

This command enables agents to work with the Forma data model definition format. The hub format (`.forma`) describes the *shape* of data — shapes, fields, references — in a language-agnostic way. Target-specific code generation is driven by satellite documents.

## Forma Repository

This command is typically symlinked from the forma repository. To find tools and references, resolve the command file location:

```
readlink -f <path-to-this-command>
```

The forma repo root is the parent of the `commands/` directory containing this file. Tools are at `tools/` and references at `references/` relative to the repo root.

**Read when relevant** (resolve paths from the repo root):
- `references/kotlin-profile.md` — Kotlin target profile (read when generating Kotlin or creating new target profiles)
- `references/sql-profile.md` — SQL target profile (read when generating SQL or creating database schemas)
- `references/satellite-architecture.md` — Full satellite document pattern
- `spec/SPEC.md` — The core format specification (authoritative reference for spec questions)
- `examples/birdtracker.forma` — Complete working example

---

## Task Reference

| User wants to... | What to do |
|---|---|
| Define a new data model | Interview → draft `model.forma` → review with enrichment |
| Review/critique a model | Parse → run enrichment checks → suggest improvements |
| Generate code from a model | Read hub + target profile → produce target-specific output |
| Generate code via CLI | Parse `/forma` arguments → resolve satellites → generate target code |
| Validate atom coverage | Parse `/forma --validate` arguments → resolve satellites → check coverage |
| Create a target profile | Read `references/satellite-architecture.md` + example profile → draft profile |
| Add validation rules | Create `model.validate.yaml` with named contexts referencing hub shapes |
| Refine an existing model | Load → apply enrichment pipeline → propose changes with rationale |
| Validate a hub file | Run `python tools/validate.py model.forma` → fix errors → re-validate |

---

## CLI Invocation

When the user runs `/forma` with arguments, the command uses structured satellite resolution instead of relying on the user to specify files manually.

### Syntax

```
/forma <hub-file> --<target> [satellite-files...] [--validate]
```

| Argument | Required | Description |
|---|---|---|
| `<hub-file>` | Yes | Path to the `.forma` hub file |
| `--<target>` | Yes | Target language (`--kotlin`, `--sql`, `--typescript`, etc.) |
| `[satellite-files...]` | No | Explicit satellite file paths, applied after convention-discovered files |
| `--validate` | No | Run atom coverage check instead of code generation |

### Examples

**Minimal — generate Kotlin from a hub file:**
```
/forma birdtracker.forma --kotlin
```

**With an explicit satellite override:**
```
/forma birdtracker.forma --kotlin custom-atoms.yaml
```

**Validate atom coverage without generating code:**
```
/forma birdtracker.forma --kotlin --validate
```

### Satellite Resolution Order

When `/forma` is invoked, satellites are resolved in this order:

1. **Hub** — parse `<hub-file>`
2. **Convention satellite** — the file at `<stem>.<target>.yaml` in the hub's directory, auto-discovered by naming convention (no explicit argument needed)
3. **Explicit satellites** — load each `[satellite-files...]` in the order provided
4. **Layer profiles** — auto-discover `<stem>.<target>.*.yaml` (excluding already-loaded files)

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

**Resolution trace — `/forma examples/birdtracker.forma --kotlin`:**

| Step | File | Found? |
|---|---|---|
| Hub | `examples/birdtracker.forma` | Yes |
| Convention satellite | `examples/birdtracker.kotlin.yaml` | Yes |
| Explicit satellites | *(none provided)* | — |
| Layer profiles | `examples/birdtracker.kotlin.*.yaml` | *(none found)* |

**Merged satellite stack (2 files):** model-specific Kotlin profile → hub shapes.

**Resolution trace — `/forma examples/birdtracker.forma --sql`:**

| Step | File | Found? |
|---|---|---|
| Hub | `examples/birdtracker.forma` | Yes |
| Convention satellite | `examples/birdtracker.sql.yaml` | Yes |
| Explicit satellites | *(none provided)* | — |
| Layer profiles | `examples/birdtracker.sql.*.yaml` | *(none found)* |

### Resolution Rules

- **Hub stem**: derived from the hub filename by stripping the `.forma` extension. For `birdtracker.forma`, the stem is `birdtracker`.
- **Convention satellite**: `<stem>.<target>.yaml` in the hub's directory.
- **Layer profiles**: `<stem>.<target>.*.yaml` in the hub's directory, excluding files already loaded as convention or explicit satellites.

### Processing Modes

**Default mode — code generation:** After resolving and merging all satellites, proceed to the generation process (see [Generating Code](#generating-code)).

**Validate mode (`--validate`) — atom coverage check:** Instead of generating code, verify that every atom in the hub has a resolution path in the merged satellite stack.

An atom is **covered** if either of these conditions holds:
1. It appears in `type_mappings` (primitive atoms — e.g., `UUID: java.util.UUID`)
2. It appears in `emitters.atoms` (domain atoms — e.g., `BirdId: UUID`)

Per-name style overrides in emitters (e.g., `BirdId: { style: value_class }`) control *representation*, not coverage. An atom must have a base type in one of the two sections above.

**Passing example — `/forma birdtracker.forma --kotlin --validate`:**

```
Atom coverage: 11/11 covered

  string        → type_mappings: String
  text          → type_mappings: String
  int           → type_mappings: Int
  float         → type_mappings: Double
  datetime      → type_mappings: kotlinx.datetime.Instant
  json          → type_mappings: kotlinx.serialization.json.JsonElement
  UUID          → type_mappings: java.util.UUID
  bool          → type_mappings: Boolean
  BirdId        → emitters.atoms: UUID → type_mappings: java.util.UUID
  UserId        → emitters.atoms: UUID → type_mappings: java.util.UUID
  Email         → emitters.atoms: string → type_mappings: String
```

**Failing example — satellite missing some `emitters.atoms` entries and type mappings:**

```
Atom coverage: 8/11 — 3 UNMAPPED

  string        → type_mappings: String
  text          → type_mappings: String
  int           → type_mappings: Int
  float         → type_mappings: Double
  datetime      → type_mappings: kotlinx.datetime.Instant
  json          → type_mappings: kotlinx.serialization.json.JsonElement
  UUID          → type_mappings: java.util.UUID
  BirdId        → emitters.atoms: UUID → type_mappings: java.util.UUID
  UserId        → UNMAPPED
  Email         → UNMAPPED
  bool          → UNMAPPED

Errors: 3 unmapped atom(s): UserId, Email, bool
```

---

## Hub Syntax Reference

### Primitives (Atoms)

`string` `text` `int` `float` `bool` `datetime` `date` `UUID` `json`

These are atoms — the hub doesn't define them. Target profiles map them to concrete types.

### Nullability

Append `?` to any type. Non-null by default.

```forma
name: string          // required
bio: text?            // nullable
```

### Collections

```forma
tags: [string]              // collection: zero or more values
metadata: {string, json}    // association: key-value pairs
items: [string]?            // nullable collection
scores: [float?]            // nullable elements (warns)
```

Named wrappers allowed — defined in target profiles: `tree<T>`, etc.

### Field Syntax

Every field is `name: type` or `name: type?`. Nothing else in the hub.

```forma
name: string
location: Location?
tags: [string]
bird: Bird
observations: [Observation]
```

Constraints (`primary_key`, `unique`, `default`) are satellite concerns.

### `.forma` Syntax

```forma
// Line comments use double-slash
/* Block comments use slash-star (nestable) */

(namespace com.example.myapp)            // optional — logical package identity

(model AppName v1.0 "Description")

// Mixins — shared field templates (optional type params, optional composition)
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

(mixin Auditable [Timestamped]
  created_by: UserId
  updated_by: UserId?)

(mixin Versioned<T>
  current: T
  history: [T]
  version: int)

// Choices — enum-like (all bare variants)
(choice Status active archived deleted)

// Choices — union-like (fielded variants)
(choice Payment
  (common
    amount: float)
  (CreditCard
    number: string)
  (BankTransfer
    account: string)
  Cash)                        // fieldless variant (marker)

// Shapes — structured types with optional mixin fields
(shape Location
  latitude: float
  longitude: float)

(shape User [Timestamped]
  id: UserId
  email: Email
  location: Location?
  posts: [Post])

(shape Bird [Versioned<Bird> Timestamped]
  name: string
  species: string)
```

### Plural Forms

Group multiple definitions in a single form. Same IR output as singular forms.

```forma
(mixins
  (Timestamped
    created_at: datetime
    updated_at: datetime?)
  (Versioned<T>
    current: T
    history: [T]
    version: int))

(choices
  (Status active archived deleted)
  (Role admin editor viewer))

(shapes
  (Location
    latitude: float
    longitude: float)
  (User [Timestamped]
    id: UserId
    email: Email))
```

Singular and plural forms can be mixed freely.

### Cardinality Inference

Targets infer cardinality from cross-references:

| Side A | Side B | Cardinality |
|--------|--------|-------------|
| `posts: [Post]` | `author: User` | **1:N** |
| `tags: [Tag]` | `posts: [Post]` | **N:M** |
| `profile: Profile` | `user: User` | **1:1** |

---

## Satellite Architecture Essentials

The hub (`model.forma`) describes what the data *is* — pure shape. Satellite documents describe how the data is *used*, *validated*, or *represented* in specific contexts.

```
model.forma               ← Hub: structure, shapes, references
├── model.validate.yaml   ← Satellite: validation rules
├── model.kotlin.yaml     ← Satellite: Kotlin generation profile
├── model.sql.yaml        ← Satellite: SQL generation profile
└── model.kotlin.api.yaml ← Satellite: Kotlin API layer overrides
```

### Core Rules

1. **Satellites reference the hub by name.** They use shape names, field names, and choice names from the hub. They never redefine structural elements.
2. **Satellites are independently optional.** The hub is self-contained. Any satellite can be absent without invalidating the model.
3. **Satellites can stack.** A base Kotlin profile might set global immutability. A Kotlin API profile layers on serialization and DTOs. The agent merges them in order.
4. **The hub never grows for satellite concerns.** Target-specific, validation-specific, or deployment-specific features go in satellites.
5. **Hub namespace serves as default package.** If the hub declares `(namespace com.example.foo)`, generators use it as default. Satellites override via `package:`.
6. **Constraints belong in satellites.** Primary keys, unique constraints, default values, and relationship details are satellite concerns.

### Merge Order

1. **Hub** (`model.forma`) — structural truth
2. **Convention satellite** (`model.<target>.yaml`) — model-specific target profile discovered by naming convention
3. **Explicit satellites** — additional satellite files provided directly (e.g., via CLI arguments)
4. **Layer profiles** (`model.<target>.*.yaml`) — layer-specific overrides

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

### Validation Satellite

Named contexts with optional inheritance and atom-type defaults:

```yaml
validations:
  base:
    default:
      string: [max_length: 10000]
      datetime: [immutable]
    User:
      email: [format: email]
      username: [min_length: 3, max_length: 50]
  api:
    extends: base
    default:
      string: [max_length: 50000]
  persistence:
    extends: base
    default:
      string: [max_length: 255]
```

Reserved keys in a context: `extends:`, `default:`. Everything else is a shape name.

For the full satellite document pattern, read `references/satellite-architecture.md`.

---

## Defining a New Model

### 1. Interview

Gather domain information from the user. Key questions:

- What are the main things (shapes) in your domain?
- How do they relate to each other?
- What fields does each shape have?
- Are there values that are always one of a fixed set? (→ choices)
- Are there field groups that repeat across shapes? (→ mixins)
- Are there fields that can be one of several forms? (→ choices with fielded variants)
- Are there structured values used as fields? (→ shapes without identity)

### 2. Draft

Produce a `model.forma` following the spec. The `.forma` syntax is recommended for new models:

```forma
// Section order (recommended):
(namespace com.example.myapp)

(model Name v1.0 "Description")

// mixins — field templates (can compose other mixins)
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

// choices — enum-like or union-like alternatives
(choice Status active archived deleted)

// shapes — structured types
(shape User [Timestamped]
  id: UserId
  name: string)

// choices — with fielded variants
(choice Payment
  (common
    amount: float)
  (CreditCard
    number: string)
  Cash)
```

**Field rules:**
- Every field is `name: type` or `name: type?`. No constraints in the hub.
- Non-null by default. Only add `?` when the field is genuinely optional.
- Use atoms for semantic clarity — `BirdId`, `Email` instead of raw `UUID`, `string`. Target profiles map them.
- References are plain fields: `bird: Bird` or `observations: [Observation]`.

**Naming conventions:**
- Shapes: `PascalCase`
- Fields and choice variants: `snake_case`
- Mixins: `PascalCase` descriptive adjectives (`Timestamped`, `SoftDeletable`, `Auditable`)

**Validate the draft:** Run `python tools/validate.py model.forma` to check for structural errors before enrichment review. Fix any E-codes before proceeding; W-codes are informational.

### 3. Enrichment Review

After drafting, review the model systematically:

| Check | What to look for |
|---|---|
| **Repeated fields** | Same field on 3+ shapes → suggest a mixin |
| **Raw strings that could be choices** | `status: string` → should this be a choice? |
| **Missing inverse references** | `observations: [Observation]` on `Bird` but no `bird: Bird` on `Observation` |
| **Naming consistency** | Mixed casing conventions |
| **Atom opportunities** | Raw `string` fields that carry semantic meaning → use an atom name |
| **Nullable vs non-null** | Fields marked `?` that should probably be required, or vice versa |
| **Choice candidates** | Fields with comments like "can be X or Y" → choice with variants |
| **Value shape candidates** | Groups of fields that always appear together (lat/lng, street/city/zip) → shape without identity |

Present findings to the user as suggestions, not automatic changes. Explain rationale.

### When to Extract a Mixin

**Extract when:**
- 3+ shapes share the same field group
- The fields always appear together as a unit
- The group has a clear, descriptive name (`Timestamped`, `SoftDeletable`, `Auditable`)

**Leave separate when:**
- Only 2 shapes share the fields — wait until a third appears
- The fields are coincidentally similar but semantically different across shapes
- Extracting would create a single-field mixin with no clear identity

---

## Generating Code

### Prerequisites

> **CLI path**: If invoked via `/forma hub.forma --<target> [files...]`, satellite resolution is automatic. See [CLI Invocation](#cli-invocation). Skip to the generation process.

1. Read the hub (`model.forma`)
2. Read the relevant target profile (`model.{target}.yaml`)
3. If no target profile exists, ask the user about target-specific preferences or use sensible defaults

### Generation Process

1. **Resolve the model** — expand mixins into shapes (including transitive composition), validate all references
2. **Infer cardinality** — cross-reference field types between shapes to determine 1:1, 1:N, N:M relationships
3. **Apply target profile** — map types, resolve atoms, apply collection strategies, handle choice overrides, apply constraints (PK, unique, defaults)
4. **Generate output** — produce idiomatic code for the target language

### Key target-specific decisions the profile controls:

| Decision | Examples |
|---|---|
| Primary keys | Which fields are primary keys |
| Unique constraints | Which fields have unique constraints |
| Default values | Default values for fields |
| Atom representation | Kotlin: `value class` vs `typealias`; TypeScript: branded type vs raw |
| Collection types | `[T]` → `PersistentList<T>` vs `List<T>` vs `T[]`; `{K,V}` → `Map<K,V>`; named wrappers: `tree<T>` |
| Choice strategy | All-bare: enum, bitmask, sealed class. Fielded: sealed class, discriminated union |
| Nullability | Kotlin `?`, TypeScript `| null`, SQL `NULL` |
| Value shapes | Nested class, embedded document, prefixed columns |
| Serialization | `@Serializable`, `@JsonProperty`, none |
| Derived types | `Partial<T>`, `Omit<T, K>`, create/update DTOs derived from shapes |
| FK naming | `bird_id`, `birdId`, `bird_fk` |
| Join table strategy | Auto-named, explicit through shape |

### When no target profile exists

Generate with reasonable defaults and note assumptions:

```
// Generated with default settings. Consider creating a target profile for:
// - Primary key designation
// - Collection type preferences (mutable vs immutable)
// - Serialization annotations
// - Atom wrapping strategy
```

---

## Creating a Target Profile

Read `references/satellite-architecture.md` and the relevant `references/{target}-profile.md` first.

A target profile covers these sections (all optional — omit what you don't need):

```yaml
target: <language>

type_mappings:
  # How each primitive type maps to target language types

emitters:
  atoms:
    # Domain atom → base type (resolved via type_mappings)
    # Shared across all emitters in this satellite
    BirdId: UUID
    Email: string

  <name>:
    # Generation settings — package/module, immutability, collections, serialization
    package: com.example.model
    immutability: full
    nullability: strict

    shape: <style>      # Default shape representation (data_class, class, etc.)
    choice: <style>     # Default choice representation (enum_class, sealed_class, etc.)

    # Per-name overrides — generator infers concept type from hub
    # Shapes/choices: use block form with style: and extra keys
    # Atoms: use block form for style override (base type from atoms:)

derived_types:
  # Create/update/patch/summary DTOs derived from shapes

relationships:
  # FK naming, join table strategy, cardinality overrides
```

---

## Working with Satellite Documents

The hub is pure shape. Satellites reference it by shape and field name. Key rules:

- Satellites **never redefine structure** — they add target-specific or behavioral context
- Each satellite is **independently optional** — the model stands alone
- Satellites can **stack** — a Kotlin API profile can layer on top of a base Kotlin profile
- The agent loads **only the relevant satellites** for the current task

See `references/satellite-architecture.md` for the full pattern.

---

## Common Patterns

### Timestamp tracking
```forma
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)
```

### Soft delete
```forma
(mixin SoftDeletable
  deleted_at: datetime?
  is_deleted: bool)
```

### Audit trail (with mixin composition)
```forma
(mixin Auditable [Timestamped]
  created_by: UserId
  updated_by: UserId?)
```

### Media with variants
```forma
(choice Media
  (common
    url: string
    mime_type: string
    size_bytes: int)
  (Image
    width: int
    height: int)
  (Video
    duration_seconds: float
    thumbnail_url: string)
  (Document
    page_count: int?))
```

### Tree/hierarchy
```forma
(shape Category
  id: UUID
  name: string
  depth: int
  parent: Category?
  children: [Category])
```

### Status as choice
```forma
(choice OrderStatus draft pending confirmed shipped delivered cancelled)
```

---

## Diagnostic Codes

### Errors

| Code | Scope | Description |
|---|---|---|
| E000 | Parse | `.forma` parse failure (syntax error, unterminated block comment, etc.) |
| E001 | Meta | `meta` section is missing |
| E002 | Meta | `meta.name` is missing or not a string |
| E003 | Meta | `meta.version` is missing or not a string |
| E004 | Meta | `meta.namespace` is present but not a non-empty string |
| E010 | Top-level | Unknown top-level key (valid: `meta`, `shapes`, `choices`, `mixins`) |
| E011 | Structure | Section or entry is not a mapping (wrong YAML/IR type) |
| E041 | Type | Invalid field type — not a string, empty, or malformed association arity |
| E042 | Type | Mixin used as a field type (use a shape instead) |
| E050 | Choice | Choice has fewer than 2 variants |
| E051 | Choice | Variant is not a mapping or empty |
| E053 | Choice | `common` block is not a mapping |
| E060 | Mixin | Mixin is malformed — missing fields, empty fields, or unknown sub-key |
| E065 | Mixin | `type_params` is not a list, or a parameter is not a string |
| E070 | Shape | Shape is missing `fields` section or has no fields |
| E075 | Shape | Field type is not a string |
| E083 | Shape | `use` list is not a list |
| E084 | Shape | Unknown mixin referenced in shape's `use` list |
| E085 | Shape | Unknown sub-key in shape (valid: `use`, `fields`) |
| E086 | Shape | Mixin type argument arity mismatch |
| E090 | Shape | Field name conflict between two composed mixins |
| E091 | Mixin | Circular mixin composition detected |
| E092 | Mixin | `use` list is not a list, or references an unknown mixin |
| E100 | Global | Same name defined in two different sections |

### Warnings

| Code | Scope | Description |
|---|---|---|
| W012 | Shape | Shape field shadows a mixin field (shape field wins) |
| W013 | Meta | `meta.description` is missing |
| W015 | Type | Named wrapper used (e.g., `tree<T>`) — valid but noted |
| W017 | Section | Section is declared but empty |
| W019 | Type | Nullable element type inside a collection — discouraged |

---

## Bundled Tools

Two Python tools provide automated validation and parsing. Both are standalone scripts with no dependencies beyond the Python standard library. Resolve paths from the forma repo root (see [Forma Repository](#forma-repository)).

### Hub Validator

```
python tools/validate.py <model.forma>
```

Checks the hub for structural errors (E-codes) and warnings (W-codes). Exit codes: `0` = valid, `1` = errors found, `2` = bad usage.

```
$ python tools/validate.py examples/birdtracker.forma
Validating examples/birdtracker.forma ...

[OK] Model "BirdTracker" v8.0 is valid.
```

### DSL Parser

```
python tools/forma_parser.py <model.forma>
```

Parses a `.forma` file and outputs the intermediate representation as YAML. The IR contains keys `meta`, `shapes`, `choices`, and `mixins`. Useful for inspecting how the parser interprets a hub file.
