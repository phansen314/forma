---
name: forma
description: "Use this skill when the user wants to define, review, refine, or generate code from a data model. Also triggers on '/forma' command invocations with arguments. Triggers include: defining shapes, relationships, or schemas; creating or editing .forma or .yaml model files; generating data classes, ORM models, or DDL from a model; reviewing a data model for consistency; creating target profiles (Kotlin, TypeScript, SQL, etc.); or any mention of 'data model', 'schema definition', 'shapes', 'choices', 'mixins', or 'atoms' in the context of structured data modeling. Also triggers when the user wants to convert between data representations or create satellite documents (validation, target profiles). Do NOT use for general YAML editing, API endpoint design, or database administration tasks."
---

# Data Model Definition — Agent Skill

## Overview

This skill enables agents to work with the Forma data model definition format. The hub format (`.forma`) describes the *shape* of data — shapes, fields, references — in a language-agnostic way. Target-specific code generation is driven by satellite documents.

**Read before starting any task:**
- `../spec/SPEC.md` — The core format specification (required for all tasks)
- `references/satellite-architecture.md` — How satellite documents work (required when generating code or creating target profiles)

**Read when relevant:**
- `references/kotlin-profile.md` — Example target profile (read when generating Kotlin or creating new target profiles)
- `references/quick-reference.md` — One-page syntax cheat sheet
- `../examples/birdtracker.forma` — Complete working example

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

---

## CLI Invocation

When the user runs `/forma` with arguments, the skill uses structured satellite resolution instead of relying on the user to specify files manually.

### Syntax

```
/forma <hub-file> --<target> [satellite-files...] [--no-base] [--validate]
```

| Argument | Required | Description |
|---|---|---|
| `<hub-file>` | Yes | Path to the `.forma` hub file |
| `--<target>` | Yes | Target language (`--kotlin`, `--sql`, `--typescript`, etc.) |
| `[satellite-files...]` | No | Explicit satellite file paths, applied after convention-discovered files |
| `--no-base` | No | Skip auto-loading base profile from `profiles/<target>/` |
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

**Skip base profiles (model satellite is fully self-contained):**
```
/forma birdtracker.forma --kotlin --no-base
```

### Satellite Resolution Order

When `/forma` is invoked, satellites are resolved in this order:

1. **Hub** — parse `<hub-file>`
2. **Base profile** — auto-load `profiles/<target>/*.yaml` (skip if `--no-base`)
3. **Convention satellite** — auto-discover `<stem>.<target>.yaml` in the same directory as the hub
4. **Explicit satellites** — load each `[satellite-files...]` in the order provided
5. **Layer profiles** — auto-discover `<stem>.<target>.*.yaml` (excluding already-loaded files)

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

**Resolution trace — `/forma examples/birdtracker.forma --kotlin`:**

| Step | File | Found? |
|---|---|---|
| Hub | `examples/birdtracker.forma` | Yes |
| Base profile | `profiles/kotlin/kotlin-type-mappings.yaml` | Yes |
| Convention satellite | `examples/birdtracker.kotlin.yaml` | Yes |
| Explicit satellites | *(none provided)* | — |
| Layer profiles | `examples/birdtracker.kotlin.*.yaml` | *(none found)* |

**Merged satellite stack (3 files):** base type mappings → model-specific Kotlin profile → hub shapes.

**Resolution trace — `/forma examples/birdtracker.forma --sql`:**

| Step | File | Found? |
|---|---|---|
| Hub | `examples/birdtracker.forma` | Yes |
| Base profile | `profiles/sql/*.yaml` | *(none found — no base SQL profile yet)* |
| Convention satellite | `examples/birdtracker.sql.yaml` | Yes |
| Explicit satellites | *(none provided)* | — |
| Layer profiles | `examples/birdtracker.sql.*.yaml` | *(none found)* |

### Resolution Rules

- **Hub stem**: derived from the hub filename by stripping the `.forma` extension. For `birdtracker.forma`, the stem is `birdtracker`.
- **Convention satellite**: `<stem>.<target>.yaml` in the hub's directory.
- **Layer profiles**: `<stem>.<target>.*.yaml` in the hub's directory, excluding files already loaded as convention or explicit satellites.
- **Base profile directory**: `profiles/<target>/` at the project root. All `*.yaml` files in this directory are loaded.
- **`--no-base`**: Skips step 2 entirely. Useful when the model's convention satellite already includes all type mappings.

### Processing Modes

**Default mode — code generation:** After resolving and merging all satellites, proceed to the generation process (see [Generating Code](#generating-code)).

**Validate mode (`--validate`) — atom coverage check:** Instead of generating code, verify that every atom in the hub has a resolution path in the merged satellite stack.

An atom is **covered** if any of these conditions hold:
1. It appears in `type_mappings` (e.g., `UUID: java.util.UUID`)
2. It has a per-name entry in `emitters` (e.g., `BirdId: { style: value_class }`)
3. It falls back to `emitters.<gen>.default.atom` (e.g., `atom: typealias`)

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
  BirdId        → emitter override: value_class
  UserId        → emitter override: value_class
  Email         → emitter default atom: typealias  ⚠ (no explicit mapping)
  bool          → type_mappings: Boolean

Warnings: 1 atom(s) relying on emitter default only: Email
```

**Failing example — satellite missing `default.atom` and some type mappings:**

```
Atom coverage: 8/11 — 3 UNMAPPED

  string        → type_mappings: String
  text          → type_mappings: String
  int           → type_mappings: Int
  float         → type_mappings: Double
  datetime      → type_mappings: kotlinx.datetime.Instant
  json          → type_mappings: kotlinx.serialization.json.JsonElement
  UUID          → type_mappings: java.util.UUID
  BirdId        → emitter override: value_class
  UserId        → UNMAPPED
  Email         → UNMAPPED
  bool          → UNMAPPED

Errors: 3 unmapped atom(s): UserId, Email, bool
```

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

Read `references/satellite-architecture.md` and `references/kotlin-profile.md` first.

A target profile covers these sections (all optional — omit what you don't need):

```yaml
target: <language>

generators:
  <name>:
    # Named output context — package/module, immutability, collections, serialization

type_mappings:
  # How each primitive type maps to target language types

emitters:
  <name>:
    default:
      shape: <style>    # Default shape representation (data_class, class, etc.)
      choice: <style>   # Default choice representation (enum_class, sealed_class, etc.)
      atom: <style>     # Default atom representation (typealias, value_class, etc.)

    # Per-name overrides — generator infers concept type from hub
    # Shapes/choices: use block form with style: and extra keys
    # Atoms: inline scalar for type mapping (BirdId: int), block for style override

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
- **Base profiles provide defaults** — `profiles/<target>/` contains universal type mappings that form the foundation layer. Model-specific satellites layer on top.
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
