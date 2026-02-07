# Data Model Definition Format — v2

## Overview

A YAML-based format for defining data models that agents can parse, refine, and convert into language-specific code and database schemas.

## Design Principles

- **Structure, not validation**: This spec describes the *shape* of data — types, fields, relationships, and cardinality. Behavioral rules (format validation, range checks, immutability, custom expressions) belong in a separate validation satellite document.
- **Minimal boilerplate**: The common case should be short; verbosity only when expressing complex constraints
- **Agent-friendly**: Semi-structured enough for agents to parse and infer meaning, constrained enough to validate
- **Lenient parsing**: YAML structure is validated; values are parsed with warnings rather than hard failures
- **Three-stage pipeline**: Parse/validate → agent enrichment → code generation
- **Language-agnostic**: Core spec describes shape only; target profiles handle language and persistence specifics

---

## Document Architecture

The data model is defined across multiple focused documents. The core structural spec (this file) is the hub — small, target-agnostic, and concerned only with shape. Satellite documents add context for specific concerns:

```
model.yaml              ← Structure (this spec): types, fields, relationships
model.validate.yaml     ← Validation: format rules, range checks, immutability
model.kotlin.yaml       ← Kotlin target profile: collections, immutability, bitmasks
model.typescript.yaml   ← TypeScript target profile: Zod vs io-ts, ESM vs CJS
model.sql.yaml          ← SQL target profile: dialect, indexing strategy, partitioning
```

Each satellite document references entities and fields from the core spec by name. The agent loads whichever documents are relevant to the current task — generating Kotlin code pulls in `model.yaml` + `model.kotlin.yaml`; adding validation pulls in `model.yaml` + `model.validate.yaml`.

This keeps each file small and single-purpose. The core spec never grows to accommodate target-specific concerns.

---

## Type System

The spec provides six concepts for describing data shape:

| Concept | Purpose | Used as a field type? |
|---|---|---|
| **Composite types** | Named field groups — nested structures | Yes |
| **Unions** | Discriminated sum types — exactly one of several variants | Yes |
| **Enums** | Fixed set of named values | Yes |
| **Type aliases** | Semantic names for primitives | Yes (resolves to base) |
| **Mixins** | Shared field templates inlined into entities | No — field shortcut only |
| **Entities** | Domain objects with identity and relationships | Via relationships only |

These sit on top of a set of built-in primitive types and collection wrappers.

---

## Format Specification

### Top-Level Structure

```yaml
meta:
  name: string
  version: string
  description: string          # optional

composite_types:
  # Named field groups used as types

unions:
  # Discriminated sum types

enums:
  # Fixed value sets

type_aliases:
  # Semantic names for primitives

mixins:
  # Shared field templates for entities

entities:
  # Domain objects with identity and relationships
```

---

### Meta

Every model file should declare identity and version:

```yaml
meta:
  name: BirdTracker
  version: "2.0"
  description: "Bird observation tracking system"
```

---

### Primitive Types

The following base types are available without declaration:

| Type       | Description                    |
|------------|--------------------------------|
| `string`   | Short text (≤255 chars typical)|
| `text`     | Long-form text (unbounded)     |
| `int`      | Integer                        |
| `float`    | Floating-point number          |
| `bool`     | Boolean                        |
| `datetime` | Timestamp with timezone        |
| `date`     | Calendar date                  |
| `UUID`     | Universally unique identifier  |
| `json`     | Arbitrary JSON blob            |

---

### Nullability

Append `?` to any type to mark it nullable. Fields without `?` are non-null by default.

```yaml
fields:
  name: string                # required, non-null
  bio: text?                  # nullable
  deleted_at: datetime?       # nullable
  score: float?               # nullable
```

This applies to all type positions — primitives, aliases, composites, enums, unions, and collections:

```yaml
  nickname: string?
  location: Location?
  status: Status?
  payment: PaymentMethod?
  tags: list(string)?
```

---

### Collection Types

Collections use a generic wrapper syntax: `wrapper(T)` or `wrapper(K, V)`.

```yaml
fields:
  tags: list(string)
  metadata: map(string, json)
  coordinates: list(float)
  aliases: list(string)?        # the whole list is nullable
```

#### Built-in Wrappers

The core spec provides three universal wrappers:

| Wrapper        | Description              |
|----------------|--------------------------|
| `list(T)`      | Ordered collection of T  |
| `set(T)`       | Unique collection of T   |
| `map(K, V)`    | Key-value mapping        |

#### Custom Wrappers

Target profiles and satellite documents can define additional collection wrappers. The core spec treats any `name(T)` or `name(K, V)` as valid collection syntax — it doesn't restrict wrapper names to the built-in three.

For example, a Kotlin target profile might define:

```yaml
collection_wrappers:
  plist: PersistentList          # kotlinx.collections.immutable
  pset: PersistentSet
  pmap: PersistentMap
  tree: custom                   # project-specific Tree<T> implementation
```

Which enables usage in the core spec:

```yaml
fields:
  habitats: pset(Habitat)
  hierarchy: tree(Category)
  settings: pmap(string, json)
```

The core spec parser accepts any wrapper name. Target profiles define how each maps to a concrete type. Unrecognized wrappers without a target mapping produce a warning during code generation.

---

### Composite Types

Define named field groups used as types:

```yaml
composite_types:
  ScientificName:
    common: string
    scientific: string

  Location:
    latitude: float
    longitude: float
    altitude: float?

  Address:
    street: string
    city: string
    zipcode: string
    country: string
```

Composite types generate nested structures in code. Target profiles determine the concrete representation — e.g., nested data classes in Kotlin, embedded documents in MongoDB, or prefixed columns in SQL.

Nullability within composites follows the same `?` convention. A nullable composite field (`location: Location?`) means the entire group can be null; a nullable member within (`altitude: float?`) means that member alone can be null.

---

### Unions

Define discriminated sum types — a value that is exactly one of several named variants. Inspired by TypeScript discriminated unions and Kotlin sealed class hierarchies.

```yaml
unions:
  PaymentMethod:
    CreditCard:
      card_number: string
      expiry: date
      cvv: string
    BankTransfer:
      account_number: string
      routing_number: string
    Crypto:
      wallet_address: string
      network: string

  Shape:
    Circle:
      radius: float
    Rectangle:
      width: float
      height: float
    Triangle:
      base: float
      height: float
```

Each variant is a named type with its own fields. Unions are used as field types:

```yaml
entities:
  Order:
    fields:
      id: [UUID, primary_key]
      payment: PaymentMethod
      total: float
```

#### Shared fields

Variants can share common fields by declaring a `common` block:

```yaml
unions:
  Notification:
    common:
      id: UUID
      timestamp: datetime
      read: [bool, default: false]
    Email:
      subject: string
      body: text
    SMS:
      phone_number: string
      message: string
    Push:
      title: string
      deep_link: string?
```

Common fields exist on every variant. This is the structural equivalent of a base class in a sealed hierarchy — every `Notification` has `id`, `timestamp`, and `read`, regardless of variant.

#### Rules

- **Unions are types.** They can be used anywhere a type is expected: entity fields, composite type fields, even within other unions.
- **Variants are not standalone entities.** They exist only as members of their union. If a variant needs its own relationships or identity, it should be an entity with a relationship to a wrapper entity instead.
- **Nullable unions work as expected.** `payment: PaymentMethod?` means the field can be null *or* one of the variants.
- **Target profiles decide representation.** A Kotlin profile maps this to `sealed class` + `data class` variants. TypeScript maps to discriminated unions. SQL might use a `type` discriminator column + nullable variant columns, or a JSONB column — that's a target profile decision.

---

### Enums

Define fixed sets of named values:

```yaml
enums:
  ConservationStatus: [least_concern, vulnerable, endangered, critical, extinct]
  
  Habitat:
    - forest
    - wetland
    - grassland
    - coastal
    - urban
```

Both inline list and expanded list syntaxes are accepted. Enum values are plain identifiers — target profiles handle casing conventions per language.

---

### Type Aliases

Map semantic names to underlying types:

```yaml
type_aliases:
  BirdId: UUID
  UserId: UUID
  Email: string
  Url: string
```

Aliases provide semantic clarity without creating new structural types. They resolve to their base type during code generation. Target profiles control how aliases are represented — e.g., transparent type aliases, branded types, or zero-cost wrapper types like Kotlin's `@JvmInline value class`.

---

### Mixins

Shared field templates that get inlined into entities. Mixins have no identity and are never instantiated — they're purely structural shortcuts to avoid repeating field groups.

```yaml
mixins:
  Timestamped:
    created_at: datetime
    updated_at: datetime?

  SoftDeletable:
    deleted_at: datetime?
    is_deleted: [bool, default: false]

  Auditable:
    created_by: UserId
    updated_by: UserId?
```

Entities pull in mixins with `use`:

```yaml
entities:
  Bird:
    use: [Timestamped, SoftDeletable]
    fields:
      id: [BirdId, primary_key]
      name: ScientificName
```

`Bird` now has `id`, `name`, `created_at`, `updated_at`, `deleted_at`, and `is_deleted`. Mixin fields are merged into the entity as if they were declared inline.

#### Rules

- **Multiple mixins allowed.** An entity can use any number of mixins.
- **No nesting.** Mixins cannot use other mixins — keep it flat and explicit.
- **Field conflicts are errors.** If two mixins define the same field name, or a mixin field collides with an entity field, the parser warns. The entity's own field wins.
- **Mixins are not types.** You cannot use a mixin name as a field type. `location: Timestamped` is invalid — use composite types for typed field groups.

#### Mixins vs composite types

These serve different purposes:

- **Composite types** define a *nested structure* used as a field type. `location: Location` creates a `Location` value *inside* the entity.
- **Mixins** define *fields that merge into* the entity. `use: [Timestamped]` adds `created_at` and `updated_at` as top-level fields on the entity.

The test: "Is this a value I'd reference as a type?" → composite type. "Are these fields I want on multiple entities?" → mixin.

---

### Entities

Entities are domain objects with identity and relationships:

```yaml
entities:
  Bird:
    use: [Timestamped]
    fields:
      id: [BirdId, primary_key]
      name: ScientificName
      status: ConservationStatus
      habitat: Habitat?
      description: text?
      wingspan_cm: float?
      
    relationships:
      observations: { target: Observation, cardinality: one_to_many }

  Observation:
    use: [Timestamped]
    fields:
      id: [UUID, primary_key]
      timestamp: datetime
      location: Location?
      notes: text?
      count: [int, default: 1]

    relationships:
      bird: { target: Bird, cardinality: many_to_one }
      observer: { target: User, cardinality: many_to_one }
```

#### Field Syntax

Fields support two forms:

**Simple** — just a type, no constraints:
```yaml
name: ScientificName
description: text?
```

**Constrained** — type + constraints as a list:
```yaml
id: [BirdId, primary_key]
username: [string, unique]
count: [int, default: 1]
```

The first element is always the type (with optional `?` suffix). Remaining elements are constraints.

#### Built-in Constraints

| Constraint         | Meaning                                            |
|--------------------|----------------------------------------------------|
| `primary_key`      | Primary key (implies non-null, unique)             |
| `unique`           | Unique constraint                                  |
| `default: <value>` | Default value                                      |

These constraints describe **structure**, not validation. The spec intentionally excludes behavioral constraints like immutability, range checks, format validation, or custom expressions — those belong in a separate validation satellite document.

> **Note on `required`**: There is no explicit `required` constraint. Non-null is the default. Use `?` to opt into nullability. This eliminates redundancy — if you declared a type without `?`, it's required.

#### Relationships

```yaml
relationships:
  observations: { target: Observation, cardinality: one_to_many }
  bird: { target: Bird, cardinality: many_to_one }
```

Supported cardinalities: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`

#### Foreign Key Derivation

**Relationships are the source of truth — foreign keys are derived by target profiles.**

The core spec declares the relationship. How it's physically represented — FK column names, join table naming, whether a FK field even exists — is determined by the target profile during code generation.

For example, `bird: { target: Bird, cardinality: many_to_one }` might become:
- A `bird_id: UUID` column in a SQL profile
- A direct object reference in a Kotlin data class
- A `birdId: ID!` field in a GraphQL schema

SQL and ORM target profiles can provide overrides for FK naming, join table naming, and other physical storage decisions. See individual target profile documents for specifics.

---

## Processing Pipeline

### Stage 1: Parse & Validate

- Parse YAML structure
- Validate top-level keys and entity shapes
- Resolve type aliases to base types
- Expand composite types into their member fields
- Validate all referenced types, entities, and union variants exist
- Expand mixins into target entities and check for field conflicts
- Collect warnings for anything non-fatal (unknown constraints, unusual patterns)

**Output**: A normalized intermediate representation (JSON or typed dataclass tree).

### Stage 2: Agent Enrichment

The agent receives the parsed IR and performs interactive refinement. This is a conversational step — the agent may ask clarifying questions or propose changes.

**What the agent does:**

| Task | Example |
|------|---------|
| **Flag ambiguities** | "Field `count` on `Observation` — is this the number of birds spotted, or something else? Consider renaming to `birds_spotted`." |
| **Infer missing info** | "Adding `created_at: datetime` and `updated_at: datetime?` to all entities as a common pattern." |
| **Suggest type promotions** | "Field `status: string` could be an enum. Want me to create `ConservationStatus`?" |
| **Suggest mixins** | "Entities `User`, `Bird`, and `Observation` all declare `created_at: datetime`. Extract to a `Timestamped` mixin?" |
| **Validate relationships** | "You have `one_to_many` from `Bird` → `Observation` but no inverse. Adding `many_to_one` on `Observation`." |
| **Check naming consistency** | "Entities use PascalCase but `bird_meta` is snake_case — normalizing to `BirdMeta`." |

**Contract**: The agent operates on the IR and produces a revised IR plus a changelog of modifications and rationale. If clarification is needed, it pauses and prompts the user before proceeding.

### Stage 3: Code Generation

The agent reads the finalized IR alongside the relevant target profile(s) and generates output. The target profile determines what gets generated — data classes, ORM models, DDL scripts, schema definitions, etc. See individual target profile documents for specifics.

---

## Complete Example

```yaml
meta:
  name: BirdTracker
  version: "2.0"
  description: "Bird observation tracking system"

composite_types:
  ScientificName:
    common: string
    scientific: string

  Location:
    latitude: float
    longitude: float
    altitude: float?

unions:
  MediaAttachment:
    common:
      url: string
      caption: string?
    Photo:
      width: int
      height: int
    Audio:
      duration_seconds: float
      format: string

enums:
  ConservationStatus: [least_concern, vulnerable, endangered, critical, extinct]
  Habitat: [forest, wetland, grassland, coastal, urban]

type_aliases:
  BirdId: UUID
  UserId: UUID
  Email: string

mixins:
  Timestamped:
    created_at: datetime
    updated_at: datetime?

entities:
  User:
    use: [Timestamped]
    fields:
      id: [UserId, primary_key]
      username: [string, unique]
      email: [Email, unique]

    relationships:
      observations: { target: Observation, cardinality: one_to_many }

  Bird:
    use: [Timestamped]
    fields:
      id: [BirdId, primary_key]
      name: ScientificName
      status: ConservationStatus
      habitats: list(Habitat)
      description: text?
      wingspan_cm: float?
      photo_url: string?

    relationships:
      observations: { target: Observation, cardinality: one_to_many }
      tags: { target: Tag, cardinality: many_to_many }

  Observation:
    use: [Timestamped]
    fields:
      id: [UUID, primary_key]
      timestamp: datetime
      location: Location?
      notes: text?
      count: [int, default: 1]
      media: MediaAttachment?

    relationships:
      bird: { target: Bird, cardinality: many_to_one }
      observer: { target: User, cardinality: many_to_one }

  Tag:
    fields:
      id: [UUID, primary_key]
      label: [string, unique]

    relationships:
      birds: { target: Bird, cardinality: many_to_many }
```

---

## Changes from v1

| Area | v1 | v2 | Rationale |
|------|----|----|-----------|
| **Entity fields** | List of single-key dicts | Named map under `fields:` | Direct key lookup, no duplicates, cleaner parse |
| **Nullability** | `required` constraint | `?` suffix (non-null default) | Less boilerplate — the common case (non-null) is the short case |
| **Composite types** | Tuple string `(k: v, ...)` | YAML map | Native YAML, no custom parser needed |
| **Unions** | Not supported | `unions:` top-level block | Discriminated sum types for variant data |
| **Enums** | Not supported | `enums:` top-level block | Essential for real-world schemas |
| **Mixins** | Not supported | `mixins:` + `use:` | Shared field templates without inheritance |
| **Collections** | Not supported | `list(T)`, `set(T)`, `map(K,V)` | Necessary for tags, metadata, etc. |
| **Foreign keys** | Manual + relationship (redundant) | Derived by target profiles from relationships | Single source of truth; physical representation is an emitter concern |
| **Relationships** | Mixed into field list | Separate key at entity level | Structurally consistent, not ambiguous |
| **Default values** | Not supported | `default: <value>` constraint | Common need |
| **Meta block** | Not present | `meta:` with name/version | Identity and versioning |
| **Agent enrichment** | One bullet list | Detailed task table + contract | Core differentiator deserves specificity |
| **Type/constraint mappings** | In core spec | Moved to target profiles | Target-specific concerns don't belong in structural spec |
| **Document architecture** | Single file | Hub + satellite files | Keeps core small; validation, target, and deployment concerns live in separate docs |
| **Scope** | Implicit | Structure only; validation is separate | Keeps spec focused and small |
