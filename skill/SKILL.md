---
name: forma
description: "Use this skill when the user wants to define, review, refine, or generate code from a data model. Triggers include: defining shapes, relationships, or schemas; creating or editing .forma or .yaml model files; generating data classes, ORM models, or DDL from a model; reviewing a data model for consistency; creating target profiles (Kotlin, TypeScript, SQL, etc.); or any mention of 'data model', 'schema definition', 'shapes', 'choices', 'mixins', or 'atoms' in the context of structured data modeling. Also triggers when the user wants to convert between data representations or create satellite documents (validation, target profiles). Do NOT use for general YAML editing, API endpoint design, or database administration tasks."
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
| Create a target profile | Read `references/satellite-architecture.md` + example profile → draft profile |
| Add validation rules | Create `model.validate.yaml` satellite referencing hub shapes |
| Refine an existing model | Load → apply enrichment pipeline → propose changes with rationale |

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

globals:
  # Package/module, immutability strategy, serialization library

type_mappings:
  # How each primitive type maps to target language types

shapes:
  # Shape representation + per-shape overrides (style, annotations, interfaces)
  # Primary key designations, unique constraints, default values

atoms:
  # How atoms are represented (transparent, branded, wrapped)

collection_wrappers:
  collection:
    # How [T] maps to target list/array types
  association:
    # How {K,V} maps to target map/dict types

choices:
  # Default representation (enum class for all-bare, sealed class for fielded)

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
