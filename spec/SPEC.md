# Data Model Definition Format — v7

## Overview

A format for defining data models that agents can parse, refine, and convert into language-specific code and database schemas.

The hub format is **`.forma`** — a custom DSL using S-expression syntax. Every declaration is a parenthesized form: `(keyword name ...body...)`.

Satellite documents (validation, target profiles) are YAML.

## Design Principles

- **Structure, not validation**: This spec describes the *shape* of data — types, fields, and references. Behavioral rules (format validation, range checks, immutability) belong in a validation satellite document.
- **Pure shape in the hub**: The hub describes *what data is*. Constraints (`primary_key`, `unique`, `default`), relationship cardinality declarations, and foreign key derivation are satellite concerns — they describe how data is *used* or *stored*.
- **Minimal boilerplate**: The common case should be short; verbosity only when expressing complex constraints
- **Agent-friendly**: Semi-structured enough for agents to parse and infer meaning, constrained enough to validate
- **Three-stage pipeline**: Parse/validate → agent enrichment → code generation
- **Language-agnostic**: Core spec describes shape only; target profiles handle language and persistence specifics

---

## Document Architecture

The data model is defined across multiple focused documents. The hub (`.forma`) is small, target-agnostic, and concerned only with shape. Satellite documents add context for specific concerns:

```
model.forma              ← Structure (hub): types, fields, references
model.validate.yaml      ← Validation: format rules, range checks, identity, constraints
model.kotlin.yaml        ← Kotlin target profile: collections, immutability
model.typescript.yaml    ← TypeScript target profile: Zod vs io-ts, ESM vs CJS
model.sql.yaml           ← SQL target profile: dialect, indexing strategy, PK/FK/unique
```

Each satellite document references types and fields from the hub by name. The agent loads whichever documents are relevant to the current task — generating Kotlin code pulls in the hub + `model.kotlin.yaml`; adding validation pulls in the hub + `model.validate.yaml`.

This keeps each file small and single-purpose. The hub never grows to accommodate satellite concerns.

---

## Type System

The spec provides five concepts for describing data shape:

| Concept | Purpose | Used as a field type? |
|---|---|---|
| **Types** | Named structured types with optional mixin fields | Yes |
| **Unions** | Discriminated sum types — exactly one of several variants | Yes |
| **Enums** | Fixed set of named values | Yes |
| **Type aliases** | Named synonyms for other types | Yes (resolves to target) |
| **Mixins** | Shared field templates inlined into types | No — field shortcut only |

These sit on top of two structural primitives for grouping values: `[T]` (collection) and `{K, V}` (association), plus optional named wrappers like `tree<T>`.

---

## Syntax

The `.forma` format uses S-expression syntax — every declaration is a parenthesized form `(keyword name ...body...)`. This eliminates YAML scaffolding and reduces the token set to a minimum.

### Grammar (EBNF)

```ebnf
file           = { comment | form } EOF ;
form           = "(" ( model_form | alias_form | aliases_form
                     | mixin_form | mixins_form
                     | enum_form | enums_form
                     | type_form | types_form
                     | union_form | unions_form ) ")" ;

model_form     = "model" IDENT version [ STRING ] ;
version        = IDENT ;
alias_form     = "alias" IDENT IDENT ;
aliases_form   = "aliases" { IDENT IDENT } ;
mixin_form     = "mixin" IDENT [ "<" IDENT { "," IDENT } ">" ] { field } ;
mixins_form    = "mixins" { "(" IDENT [ "<" IDENT { "," IDENT } ">" ] { field } ")" } ;
enum_form      = "enum" IDENT { IDENT } ;
enums_form     = "enums" { "(" IDENT { IDENT } ")" } ;
type_form      = "type" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field } ;
types_form     = "types" { "(" IDENT [ "[" mixin_ref { mixin_ref } "]" ] { field } ")" } ;
union_form     = "union" IDENT { common_form | variant } ;
unions_form    = "unions" { "(" IDENT { common_form | variant } ")" } ;
common_form    = "(" "common" { field } ")" ;
variant        = IDENT | "(" IDENT { field } ")" ;

mixin_ref      = IDENT [ "<" type_expr { "," type_expr } ">" ] ;
field          = IDENT ":" type_expr ;
type_expr      = base_type [ "?" ] ;
base_type      = IDENT [ "<" type_expr { "," type_expr } ">" ]
               | "[" type_expr { "," type_expr } "]"
               | "{" type_expr "," type_expr "}" ;

comment        = "//" { any } EOL ;
STRING         = '"' { any } '"' ;
IDENT          = letter { letter | digit | "_" | "." } ;
```

Parentheses delimit forms. Brackets serve two roles: anonymous collections (`[T]`) and mixin lists on types (`[Timestamped]`). Braces delimit anonymous associations (`{K, V}`). Angle brackets delimit type parameters (`tree<T>`, `Versioned<Bird>`). Commas appear inside collections, associations, and generic argument lists.

### Comments

```forma
// Line comments use double-slash
```

### Model Declaration

```forma
(model BirdTracker v7.0 "Bird observation tracking system")
```

One form declares the model name, version, and optional description.

### Type Aliases

```forma
(alias BirdId UUID)
(alias UserId UUID)
(alias Email string)
```

Aliases provide semantic clarity without creating new structural types. They resolve to their base type during code generation. Target profiles control how aliases are represented — e.g., transparent type aliases, branded types, or zero-cost wrapper types like Kotlin's `@JvmInline value class`.

### Mixins

```forma
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)
```

Types pull in mixin fields with a bracket list after the name:

```forma
(type User [Timestamped]
  id: UserId
  username: string)
```

`User` now has `id`, `username`, `created_at`, and `updated_at`.

#### Generic Mixins

Mixins can declare type parameters in angle brackets. The type parameters are substituted with concrete types when the mixin is applied:

```forma
(mixin Versioned<T>
  current: T
  history: [T]
  version: int)

(type Bird [Versioned<Bird> Timestamped]
  name: string
  species: Species)
```

`Bird` now has `current: Bird`, `history: [Bird]`, `version: int`, plus the `Timestamped` fields. Multiple type parameters are comma-separated: `<T, U>`.

#### Rules

- **Multiple mixins allowed.** A type can use any number of mixins.
- **No nesting.** Mixins cannot use other mixins — keep it flat and explicit.
- **Mixin–mixin conflicts are errors.** If two mixins define the same field name, this is an error. Rename one field or extract a shared mixin.
- **Type fields shadow mixin fields.** If a type declares a field that also exists in a mixin, the type's own field wins. The validator emits a warning.
- **Mixins are not types.** You cannot use a mixin name as a field type. `location: Timestamped` is invalid — use a type for typed field groups.
- **Generic arity is checked.** If a mixin declares type parameters, the mixin reference must supply the same number of type arguments. `[Versioned]` is an error if `Versioned` requires one type argument.
- **No type parameter constraints.** No bounds like `<T: Timestamped>`. Bounds are a behavioral concern — keep the hub simple.

#### Mixins vs types

These serve different purposes:

- **Types** define a *named structure* used as a field type. `location: Location` creates a `Location` value *inside* the parent type.
- **Mixins** define *fields that merge into* the type. `[Timestamped]` adds `created_at` and `updated_at` as top-level fields on the type.

The test: "Is this a value I'd reference as a type?" → type. "Are these fields I want on multiple types?" → mixin.

### Enums

```forma
(enum ConservationStatus least_concern vulnerable endangered critical extinct)
(enum Habitat forest wetland grassland coastal urban)
```

Space-separated values inside the form. Enum values are plain identifiers — target profiles handle casing conventions per language.

### Types

```forma
(type Location
  latitude: float
  longitude: float
  altitude: float?)

(type Bird [Timestamped]
  id: BirdId
  name: ScientificName
  status: ConservationStatus
  habitats: [Habitat]
  description: text?
  observations: [Observation]
  tags: [Tag])
```

Every field is `name: type` or `name: type?`. Nothing else in the hub.

**References are just fields.** `observations: [Observation]` and `bird: Bird` are enough — targets cross-reference field types across type definitions to infer cardinality (see [Cardinality Inference](#cardinality-inference)).

**Type names.** Field types can be any declared name (types, unions, enums, type aliases) or any undeclared name that a target profile maps. The format does not restrict the set of usable type names — type resolution is a target concern. Common conventions include `string`, `int`, `float`, `bool`, `text`, `datetime`, `date`, `UUID`, and `json`, but these are conventions, not a closed set.

### Unions

```forma
(union MediaAttachment
  (common
    url: string
    caption: string?)
  (Photo
    width: int
    height: int)
  (Audio
    duration_seconds: float
    format: string))
```

The `(common ...)` sub-form defines fields shared by all variants. Variant sub-forms define variant-specific fields. Fieldless variants are bare identifiers — no sub-form needed:

```forma
(union Result
  (Success
    data: string)
  NotFound
  Unauthorized)
```

`NotFound` and `Unauthorized` are empty variants (bare identifiers without a sub-form).

#### Rules

- **Unions are types.** They can be used anywhere a type is expected: type fields, other unions, etc.
- **Variants are not standalone types.** They exist only as members of their union.
- **Nullable unions work as expected.** `payment: PaymentMethod?` means the field can be null *or* one of the variants.
- **Fieldless variants are allowed.** A variant with no fields acts as a marker/tag.
- **Variant fields follow standard rules.** Fields inside variants (and common blocks) support the same syntax as type fields, including nullability (`caption: string?`).
- **Target profiles decide representation.** A Kotlin profile maps this to `sealed class` + `data class` variants. TypeScript maps to discriminated unions. SQL might use a discriminator column — that's a target profile decision.

### Plural Forms

Every singular keyword has a plural counterpart (`aliases`, `enums`, `mixins`, `types`, `unions`) that groups multiple definitions into a single form. The plural form produces the same IR — it is purely a surface-syntax convenience.

**Aliases** use flat identifier pairs (each alias is exactly two tokens):

```forma
(aliases
  BirdId int
  BonusId int
  GoalId int)
```

**Enums, mixins, types, and unions** use parenthesized sub-forms:

```forma
(enums
  (Color white brown pink teal yellow)
  (Habitat forest wetland grassland))

(mixins
  (Timestamped
    created_at: datetime
    updated_at: datetime?)
  (Auditable
    changed_by: string))

(types
  (Location
    latitude: float
    longitude: float)
  (User [Timestamped]
    id: UserId
    name: string))

(unions
  (Result
    (Success data: string)
    NotFound
    Unauthorized)
  (DiceFace
    InvertebrateFace
    FishFace
    RodentFace))
```

Singular and plural forms can be mixed freely in the same file.

---

## Nullability

Append `?` to any type to mark it nullable. Fields without `?` are non-null by default.

```forma
name: string                // required, non-null
bio: text?                  // nullable
deleted_at: datetime?       // nullable
score: float?               // nullable
```

This applies to all type positions — aliases, types, enums, unions, and collections:

```forma
nickname: string?
location: Location?
status: Status?
payment: PaymentMethod?
tags: [string]?
```

### Element-level nullability

The `?` suffix applies to the type position it is attached to. When used inside a collection, it makes the *element* type nullable, not the collection itself:

```forma
tags: [string]          // non-null collection of non-null strings
tags: [string]?         // nullable collection of non-null strings
tags: [string?]         // non-null collection of nullable strings (warning)
tags: [string?]?        // nullable collection of nullable strings (warning)
```

The same applies to associations:

```forma
metadata: {string, json}    // non-null association
metadata: {string, json}?   // nullable association
```

Nullable collection elements are valid but discouraged — the validator emits a warning. Most targets handle null elements poorly; prefer filtering nulls out or using a sentinel value.

---

## Structural Primitives

The hub provides two anonymous structural primitives for grouping values. These describe *shape* — "zero or more values" and "key-value pairs" — without implying behavioral semantics like ordering, uniqueness, or lookup strategy.

```forma
tags: [string]                // collection: zero or more strings
metadata: {string, json}      // association: string-keyed json values
coordinates: [float]
aliases: [string]?            // nullable collection
nicknames: [string?]          // nullable elements (validator warns)
```

### Collection: `[T]`

`[T]` means "zero or more values of type T." The hub makes no claim about ordering or uniqueness — those are target concerns. A Kotlin profile might map `[T]` to `PersistentList<T>`, an SQL profile to a join table, a TypeScript profile to `T[]`.

### Association: `{K, V}`

`{K, V}` means "key-value pairs of type K to type V." Always exactly two type arguments. The hub makes no claim about lookup behavior or implementation — targets decide whether this becomes a `Map<K, V>`, a JSONB column, or a separate table.

```forma
settings: {string, json}?     // nullable association
headers: {string, string}     // string-to-string pairs
```

### Named Wrappers

Target profiles can define named wrappers for domain-specific structures. The core spec treats any `name<T>` or `name<K, V>` as valid wrapper syntax — angle brackets are the universal delimiter for type parameterization.

For example, a Kotlin target profile might define:

```yaml
collection_wrappers:
  tree: com.example.collections.Tree
```

Which enables usage in the hub:

```forma
hierarchy: tree<Category>
```

The hub parser accepts any wrapper name. Target profiles define how each maps to a concrete type. Unrecognized wrappers without a target mapping produce a warning during code generation.

`[T]` and `{K, V}` are shorthand for `coll<T>` and `dict<K, V>` respectively. Users *can* write `coll<string>` explicitly — it's valid but the shorthand `[string]` is preferred and idiomatic.

---

## Cardinality Inference

With references as plain field types, targets infer relationship cardinality by cross-referencing types:

| Side A | Side B | Inferred cardinality |
|--------|--------|---------------------|
| `observations: [Observation]` | `bird: Bird` | **1:N** — collection vs single reference |
| `tags: [Tag]` | `birds: [Bird]` | **N:M** — collection on both sides |
| `profile: Profile` | `user: User` | **1:1** — single reference on both sides |

The hub declares structure. The target profile decides how to physically represent it — FK columns, join tables, object references, etc.

---

## What Satellites Declare

The hub is pure shape. These concerns belong in satellites:

| Concern | Satellite | Example |
|---------|-----------|---------|
| Primary keys | Target profile | `User: { primary_key: id }` |
| Unique constraints | Target profile or validation | `User: { unique: [username, email] }` |
| Default values | Target profile or validation | `Observation: { defaults: { count: 1 } }` |
| FK column naming | Target profile | `fk_pattern: "{field}_id"` |
| Join table strategy | Target profile | `many_to_many: auto_join_table` |
| Format validation | Validation satellite | `email: [format: email]` |
| Range checks | Validation satellite | `wingspan_cm: [min: 1, max: 500]` |
| Immutability | Validation satellite | `created_at: [immutable]` |

---

## Processing Pipeline

```mermaid
flowchart LR
    subgraph Input
        HUB[model.forma<br/>Hub: structure]
        VAL[model.validate.yaml<br/>Validation rules]
        TGT[model.target.yaml<br/>Target profile]
        LYR[model.target.layer.yaml<br/>Layer overrides]
    end

    subgraph Stage1[Stage 1: Parse & Validate]
        S1[Parse hub<br/>Resolve aliases<br/>Expand mixins<br/>Validate references]
    end

    subgraph Stage2[Stage 2: Agent Enrichment]
        S2[Flag ambiguities<br/>Suggest improvements<br/>Validate cross-references]
    end

    subgraph Stage3[Stage 3: Code Generation]
        S3[Apply type mappings<br/>Infer cardinality<br/>Apply target rules<br/>Emit output]
    end

    OUT[Generated Output<br/>Code / DDL / Schema]

    HUB --> S1
    VAL -.-> S2
    S1 --> S2
    S2 --> S3
    TGT -.-> S3
    LYR -.-> S3
    S3 --> OUT
```

### Stage 1: Parse & Validate

- Parse hub (`.forma` DSL)
- Validate top-level structure and type shapes
- Resolve type aliases to base types
- Expand types into their member fields
- Validate all referenced types and union variants exist
- Expand mixins into target types and check for field conflicts
- Collect warnings for anything non-fatal (unknown types, unusual patterns)

**Output**: A normalized intermediate representation (JSON or typed dataclass tree).

### Stage 2: Agent Enrichment

The agent receives the parsed IR and performs interactive refinement. This is a conversational step — the agent may ask clarifying questions or propose changes.

**What the agent does:**

| Task | Example |
|------|---------|
| **Flag ambiguities** | "Field `count` on `Observation` — is this the number of birds spotted, or something else? Consider renaming to `birds_spotted`." |
| **Infer missing info** | "Adding `created_at: datetime` and `updated_at: datetime?` to all types as a common pattern." |
| **Suggest type promotions** | "Field `status: string` could be an enum. Want me to create `ConservationStatus`?" |
| **Suggest mixins** | "Types `User`, `Bird`, and `Observation` all declare `created_at: datetime`. Extract to a `Timestamped` mixin?" |
| **Validate cross-references** | "You have `[Observation]` on `Bird` but no `bird: Bird` on `Observation`. Adding inverse reference." |
| **Check naming consistency** | "Types use PascalCase but `bird_meta` is snake_case — normalizing to `BirdMeta`." |

**Contract**: The agent operates on the IR and produces a revised IR plus a changelog of modifications and rationale. If clarification is needed, it pauses and prompts the user before proceeding.

### Stage 3: Code Generation

The agent reads the finalized IR alongside the relevant target profile(s) and generates output. The target profile determines what gets generated — data classes, ORM models, DDL scripts, schema definitions, etc. See individual target profile documents for specifics.

---

## Complete Example

```forma
// BirdTracker — Example Data Model

(model BirdTracker v7.0 "Bird observation tracking system")

(alias BirdId UUID)
(alias UserId UUID)
(alias Email string)

(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

(enum ConservationStatus least_concern vulnerable endangered critical extinct)

(enum Habitat forest wetland grassland coastal urban)

(type ScientificName
  common: string
  scientific: string)

(type Location
  latitude: float
  longitude: float
  altitude: float?)

(type User [Timestamped]
  id: UserId
  username: string
  email: Email
  observations: [Observation])

(type Bird [Timestamped]
  id: BirdId
  name: ScientificName
  status: ConservationStatus
  habitats: [Habitat]
  description: text?
  wingspan_cm: float?
  photo_url: string?
  metadata: {string, json}?
  observations: [Observation]
  tags: [Tag])

(type Observation [Timestamped]
  id: UUID
  timestamp: datetime
  location: Location?
  notes: text?
  count: int
  media: MediaAttachment?
  bird: Bird
  observer: User)

(type Tag
  id: UUID
  label: string
  birds: [Bird])

(union MediaAttachment
  (common
    url: string
    caption: string?)
  (Photo
    width: int
    height: int)
  (Audio
    duration_seconds: float
    format: string))
```

---

## Changes from v6

| Area | v6 | v7 | Rationale |
|------|----|----|-----------|
| **Generics syntax** | Brackets: `tree[Category]` | Angle brackets: `tree<Category>` | Unifies type parameterization under `<>`, freeing `[]` exclusively for structural grouping (collections and mixin lists). Eliminates ambiguity with nested brackets. |
| **Generic mixins** | Not supported | `(mixin Versioned<T> current: T ...)` | Enables reusable parameterized field templates. `[Versioned<Bird>]` is unambiguous with `<>` inside `[]`. |
| **Mixin refs in types** | `[Name]` only | `[Name<Type>]` optional | Mixin references can now carry type arguments for generic mixins. |
| **Shorthand sugar** | `[T]`, `{K, V}` are structural primitives | `[T]` = `coll<T>`, `{K, V}` = `dict<K, V>` — sugar for built-in generic types | Collections and associations are now understood as shorthand for explicit generic forms. The shorthands remain idiomatic. |
| **Token count** | 10 token types | 12 token types | Added `<` and `>` for generic type parameters |

## Changes from v5

| Area | v5 | v6 | Rationale |
|------|----|----|-----------|
| **Collection syntax** | Named wrappers: `list[T]`, `set[T]` | Anonymous structural primitive: `[T]` | "Collection" — zero or more values. Ordering, uniqueness, and deduplication are target/satellite concerns, not structural claims. If `unique` belongs in a satellite, so does `set`. |
| **Association syntax** | Named wrapper: `map[K, V]` | Anonymous structural primitive: `{K, V}` | "Association" — key-value pairs. Lookup behavior is a target concern. |
| **Built-in wrappers** | `list`, `set`, `map` are special | No built-in wrappers — `list`/`set`/`map` become ordinary named wrappers if a target defines them | Simplifies the core spec; removes behavioral semantics from the hub |
| **Token count** | 8 token types | 10 token types | Added `{` and `}` for association syntax |

## Changes from v4

| Area | v4 | v5 | Rationale |
|------|----|----|-----------|
| **`.forma` syntax** | C-style curly braces (`type Foo { ... }`) | S-expression forms (`(type Foo ...)`) | Simpler parser/formatter/tooling — tokenizer becomes trivial; cleaner aesthetics for a data definition language |
| **Generic parameters** | Parentheses: `list(T)`, `map(K, V)` | Brackets: `tree[T]`, `wrapper[K, V]` | Parentheses reserved for S-expression structure; brackets for generics (later moved to `<>` in v7) |
| **Mixin inheritance** | Angle bracket: `type Foo < Mixin { ... }` | Bracket list: `(type Foo [Mixin] ...)` | Eliminates `<` token; mixin list is visually distinct from fields |
| **Enum values** | Pipe-separated: `enum X = a \| b \| c` | Space-separated: `(enum X a b c)` | Fewer token types; values are just identifiers inside the form |
| **Aliases** | Equals sign: `alias X = Y` | Juxtaposition: `(alias X Y)` | No `=` token needed |
| **Token count** | 12 token types | 8 token types | Reduced surface area: removed `{ } = \| <` |

## Changes from v3

| Area | v3 | v4 | Rationale |
|------|----|----|-----------|
| **Hub format** | YAML only | `.forma` DSL | ~20% fewer lines, zero scaffolding — every line in a type is `name: type` |
| **Constraints** | `primary_key`, `unique`, `default` in hub fields | Moved to satellites | Hub is pure shape; identity and constraints are target/validation concerns |
| **Relationships** | Explicit `relationships:` section with `target:` and `cardinality:` | References as plain field types | `[Observation]` is sufficient — targets infer cardinality from cross-references |
| **Field syntax** | Simple (`name: type`) and constrained (`name: [type, constraint]`) | Simple only (`name: type`) | Constrained form was only needed for hub constraints, which are now in satellites |
| **Type sub-keys** | `use:`, `fields:`, `relationships:` | `use:`, `fields:` | `relationships:` removed since references are fields |

## Changes from v2

| Area | v2 | v3 | Rationale |
|------|----|----|-----------|
| **Type sections** | Separate `composite_types:` and `entities:` | Single `types:` section | Persistence is a target concern — the hub should only describe structure. A type's role is determined by structural signals, not by which section it lives in. |
| **Field structure** | Fields directly under type name | `fields:` sub-key | All types share the same shape: optional `use:`, required `fields:` |
| **Type as field type** | Entities couldn't be used as field types | Any type can be a field type | Removes artificial restriction — target profiles decide representation |
| **Concept count** | Six concepts (composite types, unions, enums, type aliases, mixins, entities) | Five concepts (types, unions, enums, type aliases, mixins) | Simpler mental model |

## Changes from v1

| Area | v1 | v2 | Rationale |
|------|----|----|-----------|
| **Entity fields** | List of single-key dicts | Named map under `fields:` | Direct key lookup, no duplicates, cleaner parse |
| **Nullability** | `required` constraint | `?` suffix (non-null default) | Less boilerplate — the common case (non-null) is the short case |
| **Unions** | Not supported | `unions:` block | Discriminated sum types for variant data |
| **Enums** | Not supported | `enums:` block | Essential for real-world schemas |
| **Mixins** | Not supported | Shared field templates | Shared fields without inheritance |
| **Collections** | Not supported | Collection and association primitives | Necessary for tags, metadata, etc. |
| **Foreign keys** | Manual + relationship (redundant) | Derived by target profiles from relationships | Single source of truth; physical representation is an emitter concern |
| **Relationships** | Mixed into field list | Separate relationship declarations | Structurally consistent, not ambiguous |
| **Default values** | Not supported | `default: <value>` constraint | Common need |
| **Meta block** | Not present | `meta:` with name/version | Identity and versioning |
| **Agent enrichment** | One bullet list | Detailed task table + contract | Core differentiator deserves specificity |
| **Type/constraint mappings** | In core spec | Moved to target profiles | Target-specific concerns don't belong in structural spec |
| **Document architecture** | Single file | Hub + satellite files | Keeps core small; validation, target, and deployment concerns live in separate docs |
| **Scope** | Implicit | Structure only; validation is separate | Keeps spec focused and small |
