---
name: datamodel
description: "Use this skill when the user wants to define, review, refine, or generate code from a data model. Triggers include: defining entities, types, relationships, or schemas; creating or editing .yaml model files; generating data classes, ORM models, or DDL from a model; reviewing a data model for consistency; creating target profiles (Kotlin, TypeScript, SQL, etc.); or any mention of 'data model', 'entity', 'schema definition', 'composite types', 'unions', 'mixins', or 'type aliases' in the context of structured data modeling. Also triggers when the user wants to convert between data representations or create satellite documents (validation, target profiles). Do NOT use for general YAML editing, API endpoint design, or database administration tasks."
---

# Data Model Definition — Agent Skill

## Overview

This skill enables agents to work with a YAML-based data model definition format. The format describes the *shape* of data — types, fields, relationships — in a language-agnostic way. Target-specific code generation is driven by satellite documents.

**Read before starting any task:**
- `../spec/SPEC.md` — The core format specification (required for all tasks)
- `references/satellite-architecture.md` — How satellite documents work (required when generating code or creating target profiles)

**Read when relevant:**
- `references/kotlin-profile.md` — Example target profile (read when generating Kotlin or creating new target profiles)
- `references/quick-reference.md` — One-page syntax cheat sheet
- `../examples/birdtracker.yaml` — Complete working example

---

## Task Reference

| User wants to... | What to do |
|---|---|
| Define a new data model | Interview → draft `model.yaml` → review with enrichment |
| Review/critique a model | Parse → run enrichment checks → suggest improvements |
| Generate code from a model | Read model + target profile → produce target-specific output |
| Create a target profile | Read `references/satellite-architecture.md` + example profile → draft profile |
| Add validation rules | Create `model.validate.yaml` satellite referencing core model entities |
| Refine an existing model | Load → apply enrichment pipeline → propose changes with rationale |

---

## Defining a New Model

### 1. Interview

Gather domain information from the user. Key questions:

- What are the main things (entities) in your domain?
- How do they relate to each other?
- What fields does each entity have?
- Are there values that are always one of a fixed set? (→ enums)
- Are there field groups that repeat across entities? (→ mixins)
- Are there fields that can be one of several shapes? (→ unions)
- Are there structured values used as fields? (→ composite types)

### 2. Draft

Produce a `model.yaml` following the spec. Apply these conventions:

```yaml
# Section order:
meta:             # always first
composite_types:  # types before the things that use them
unions:
enums:
type_aliases:
mixins:
entities:         # always last — they reference everything above
```

**Field defaults:**
- Non-null by default. Only add `?` when the field is genuinely optional.
- Simple form (`name: string`) when no constraints needed.
- List form (`id: [UUID, primary_key]`) only when constraints are present.
- Use the most specific type available — prefer `Email` alias over raw `string` for email fields.

**Naming conventions:**
- Entities and types: `PascalCase`
- Fields and enum values: `snake_case`
- Mixins: `PascalCase` descriptive adjectives (`Timestamped`, `SoftDeletable`, `Auditable`)

### 3. Enrichment Review

After drafting, review the model systematically:

| Check | What to look for |
|---|---|
| **Repeated fields** | Same field on 3+ entities → suggest a mixin |
| **Raw strings that could be enums** | `status: string` → should this be an enum? |
| **Missing relationships** | One-sided `one_to_many` without inverse `many_to_one` |
| **Naming consistency** | Mixed casing conventions |
| **Type opportunities** | Raw `string` fields that carry semantic meaning → type alias |
| **Nullable vs non-null** | Fields marked `?` that should probably be required, or vice versa |
| **Union candidates** | Fields with comments like "can be X or Y" → union type |
| **Composite candidates** | Groups of fields that always appear together (lat/lng, street/city/zip) |

Present findings to the user as suggestions, not automatic changes. Explain rationale.

---

## Generating Code

### Prerequisites

1. Read the core model (`model.yaml`)
2. Read the relevant target profile (`model.{target}.yaml`)
3. If no target profile exists, ask the user about target-specific preferences or use sensible defaults

### Generation Process

1. **Resolve the model** — expand mixins into entities, resolve type aliases to base types, validate all references
2. **Apply target profile** — map types, apply collection strategies, handle enum overrides (bitmasks, sealed classes, etc.), determine union representation
3. **Generate output** — produce idiomatic code for the target language

### Key target-specific decisions the profile controls:

| Decision | Examples |
|---|---|
| Type alias representation | Kotlin: `value class` vs `typealias`; TypeScript: branded type vs raw |
| Collection types | `list(T)` → `PersistentList<T>` vs `List<T>` vs `T[]` |
| Enum strategy | Standard enum, bitmask, sealed class |
| Union representation | Kotlin: sealed class; TypeScript: discriminated union; SQL: discriminator column |
| Nullability | Kotlin `?`, TypeScript `| null`, SQL `NULL` |
| Composite types | Nested class, embedded document, prefixed columns |
| Serialization | `@Serializable`, `@JsonProperty`, none |
| Derived types | `Partial<T>`, `Omit<T, K>`, create/update DTOs |
| FK naming | `bird_id`, `birdId`, `bird_fk` |
| Join table strategy | Auto-named, explicit through entity |

### When no target profile exists

Generate with reasonable defaults and note assumptions:

```
# Generated with default settings. Consider creating a target profile for:
# - Collection type preferences (mutable vs immutable)
# - Serialization annotations
# - Type alias wrapping strategy
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

type_aliases:
  # How type aliases are represented (transparent, branded, wrapped)

collection_wrappers:
  # Built-in wrapper mappings + custom wrapper registrations

composite_types:
  # Default representation (data class, record, struct, interface)

unions:
  # Default representation (sealed class, discriminated union, tagged enum)

enums:
  # Default + overrides (standard enum, bitmask, sealed class)

entities:
  # Default style, annotations, interface implementations

derived_types:
  # Create/update/patch/summary DTOs derived from entities

relationships:
  # FK naming convention, join table strategy
```

---

## Working with Satellite Documents

The core model is the hub. Satellites reference it by entity and field name. Key rules:

- Satellites **never redefine structure** — they add target-specific or behavioral context
- Each satellite is **independently optional** — the model stands alone
- Satellites can **stack** — a Kotlin API profile can layer on top of a base Kotlin profile
- The agent loads **only the relevant satellites** for the current task

See `references/satellite-architecture.md` for the full pattern.

---

## Common Patterns

### Timestamp tracking
```yaml
mixins:
  Timestamped:
    created_at: datetime
    updated_at: datetime?
```

### Soft delete
```yaml
mixins:
  SoftDeletable:
    deleted_at: datetime?
    is_deleted: [bool, default: false]
```

### Audit trail
```yaml
mixins:
  Auditable:
    created_by: UserId
    updated_by: UserId?
```

### Media with variants
```yaml
unions:
  Media:
    common:
      url: string
      mime_type: string
      size_bytes: int
    Image:
      width: int
      height: int
    Video:
      duration_seconds: float
      thumbnail_url: string
    Document:
      page_count: int?
```

### Tree/hierarchy
```yaml
entities:
  Category:
    fields:
      id: [UUID, primary_key]
      name: string
      depth: [int, default: 0]
    relationships:
      parent: { target: Category, cardinality: many_to_one }
      children: { target: Category, cardinality: one_to_many }
```

### Status as enum
```yaml
enums:
  OrderStatus: [draft, pending, confirmed, shipped, delivered, cancelled]
```
