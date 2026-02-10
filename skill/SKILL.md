---
name: forma
description: "Use this skill when the user wants to define, review, refine, or generate code from a data model. Triggers include: defining types, relationships, or schemas; creating or editing .forma or .yaml model files; generating data classes, ORM models, or DDL from a model; reviewing a data model for consistency; creating target profiles (Kotlin, TypeScript, SQL, etc.); or any mention of 'data model', 'schema definition', 'types', 'unions', 'mixins', or 'type aliases' in the context of structured data modeling. Also triggers when the user wants to convert between data representations or create satellite documents (validation, target profiles). Do NOT use for general YAML editing, API endpoint design, or database administration tasks."
---

# Data Model Definition — Agent Skill

## Overview

This skill enables agents to work with the Forma data model definition format. The hub format (`.forma`) describes the *shape* of data — types, fields, references — in a language-agnostic way. Target-specific code generation is driven by satellite documents.

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
| Create a target profile | Read `references/satellite-architecture.md` + example profile → draft profile |
| Add validation rules | Create `model.validate.yaml` satellite referencing hub types |
| Refine an existing model | Load → apply enrichment pipeline → propose changes with rationale |

---

## Defining a New Model

### 1. Interview

Gather domain information from the user. Key questions:

- What are the main things (types) in your domain?
- How do they relate to each other?
- What fields does each type have?
- Are there values that are always one of a fixed set? (→ enums)
- Are there field groups that repeat across types? (→ mixins)
- Are there fields that can be one of several shapes? (→ unions)
- Are there structured values used as fields? (→ types without identity)

### 2. Draft

Produce a `model.forma` following the spec. The `.forma` syntax is recommended for new models:

```forma
// Section order (recommended):
(model Name v1.0 "Description")

// aliases first — they're used by later declarations
(alias UserId UUID)

// mixins — field templates
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

// enums — fixed value sets
(enum Status active inactive)

// types — structured types
(type User [Timestamped]
  id: UserId
  name: string)

// unions — discriminated sum types
(union Payment
  (CreditCard
    number: string)
  Cash)
```

**Field rules:**
- Every field is `name: type` or `name: type?`. No constraints in the hub.
- Non-null by default. Only add `?` when the field is genuinely optional.
- Use the most specific type available — prefer `Email` alias over raw `string` for email fields.
- References are plain fields: `bird: Bird` or `observations: [Observation]`.

**Naming conventions:**
- Types: `PascalCase`
- Fields and enum values: `snake_case`
- Mixins: `PascalCase` descriptive adjectives (`Timestamped`, `SoftDeletable`, `Auditable`)

### 3. Enrichment Review

After drafting, review the model systematically:

| Check | What to look for |
|---|---|
| **Repeated fields** | Same field on 3+ types → suggest a mixin |
| **Raw strings that could be enums** | `status: string` → should this be an enum? |
| **Missing inverse references** | `observations: [Observation]` on `Bird` but no `bird: Bird` on `Observation` |
| **Naming consistency** | Mixed casing conventions |
| **Type opportunities** | Raw `string` fields that carry semantic meaning → type alias |
| **Nullable vs non-null** | Fields marked `?` that should probably be required, or vice versa |
| **Union candidates** | Fields with comments like "can be X or Y" → union type |
| **Value type candidates** | Groups of fields that always appear together (lat/lng, street/city/zip) → type without identity |

Present findings to the user as suggestions, not automatic changes. Explain rationale.

---

## Generating Code

### Prerequisites

1. Read the hub (`model.forma`)
2. Read the relevant target profile (`model.{target}.yaml`)
3. If no target profile exists, ask the user about target-specific preferences or use sensible defaults

### Generation Process

1. **Resolve the model** — expand mixins into types, resolve type aliases to base types, validate all references
2. **Infer cardinality** — cross-reference field types between types to determine 1:1, 1:N, N:M relationships
3. **Apply target profile** — map types, apply collection strategies, handle enum overrides, determine union representation, apply constraints (PK, unique, defaults)
4. **Generate output** — produce idiomatic code for the target language

### Key target-specific decisions the profile controls:

| Decision | Examples |
|---|---|
| Primary keys | Which fields are primary keys |
| Unique constraints | Which fields have unique constraints |
| Default values | Default values for fields |
| Type alias representation | Kotlin: `value class` vs `typealias`; TypeScript: branded type vs raw |
| Collection types | `[T]` → `PersistentList<T>` vs `List<T>` vs `T[]`; `{K,V}` → `Map<K,V>`; named wrappers: `tree<T>` |
| Enum strategy | Standard enum, bitmask, sealed class |
| Union representation | Kotlin: sealed class; TypeScript: discriminated union; SQL: discriminator column |
| Nullability | Kotlin `?`, TypeScript `| null`, SQL `NULL` |
| Value types | Nested class, embedded document, prefixed columns |
| Serialization | `@Serializable`, `@JsonProperty`, none |
| Derived types | `Partial<T>`, `Omit<T, K>`, create/update DTOs derived from types |
| FK naming | `bird_id`, `birdId`, `bird_fk` |
| Join table strategy | Auto-named, explicit through type |

### When no target profile exists

Generate with reasonable defaults and note assumptions:

```
// Generated with default settings. Consider creating a target profile for:
// - Primary key designation
// - Collection type preferences (mutable vs immutable)
// - Serialization annotations
// - Type alias wrapping strategy
```

---

## Creating a Target Profile

Read `references/satellite-architecture.md` and `references/kotlin-profile.md` first.

A target profile covers these sections (all optional — omit what you don't need):

```yaml
target: <language>

globals:
  # Package/module, immutability strategy, serialization library

type_mappings:
  # How each primitive type maps to target language types

types:
  # Default representation + per-type overrides (style, annotations, interfaces)
  # Primary key designations, unique constraints, default values

type_aliases:
  # How type aliases are represented (transparent, branded, wrapped)

collection_wrappers:
  collection:
    # How [T] maps to target list/array types
  association:
    # How {K,V} maps to target map/dict types

unions:
  # Default representation (sealed class, discriminated union, tagged enum)

enums:
  # Default + overrides (standard enum, bitmask, sealed class)

derived_types:
  # Create/update/patch/summary DTOs derived from types

relationships:
  # FK naming convention, join table strategy, cardinality overrides
```

---

## Working with Satellite Documents

The hub is pure shape. Satellites reference it by type and field name. Key rules:

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

### Audit trail
```forma
(mixin Auditable
  created_by: UserId
  updated_by: UserId?)
```

### Media with variants
```forma
(union Media
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
(type Category
  id: UUID
  name: string
  depth: int
  parent: Category?
  children: [Category])
```

### Status as enum
```forma
(enum OrderStatus draft pending confirmed shipped delivered cancelled)
```
