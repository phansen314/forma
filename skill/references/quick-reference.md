# Data Model Format — Quick Reference

## Hub Format

`.forma` — S-expression DSL. Satellites are YAML.

## Primitives (Atoms)

`string` `text` `int` `float` `bool` `datetime` `date` `UUID` `json`

These are atoms — the hub doesn't define them. Target profiles map them to concrete types.

## Nullability

Append `?` to any type. Non-null by default.

```forma
name: string          // required
bio: text?            // nullable
```

## Collections

```forma
tags: [string]              // collection: zero or more values
metadata: {string, json}    // association: key-value pairs
items: [string]?            // nullable collection
scores: [float?]            // nullable elements (warns)
```

Named wrappers allowed — defined in target profiles: `tree<T>`, etc.

## Field Syntax

Every field is `name: type` or `name: type?`. Nothing else in the hub.

```forma
name: string
location: Location?
tags: [string]
bird: Bird
observations: [Observation]
```

Constraints (`primary_key`, `unique`, `default`) are satellite concerns.

## `.forma` Syntax

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

// Shapes — structured types with optional mixin inheritance
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

## Plural Forms

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

## Cardinality Inference

Targets infer cardinality from cross-references:

| Side A | Side B | Cardinality |
|--------|--------|-------------|
| `posts: [Post]` | `author: User` | **1:N** |
| `tags: [Tag]` | `posts: [Post]` | **N:M** |
| `profile: Profile` | `user: User` | **1:1** |

## Validation Satellite

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

## Document Architecture

```
model.forma                  ← Structure (hub)
model.validate.yaml          ← Validation rules (satellite)
model.kotlin.yaml            ← Kotlin target profile (satellite)
model.kotlin.api.yaml        ← Kotlin API layer overrides (satellite)
model.sql.yaml               ← SQL target profile (satellite)
```

## CLI Invocation

```
/forma <hub-file> --<target> [satellite-files...] [--validate]
```

Merge order: hub → `<stem>.<target>.yaml` → explicit satellites → `<stem>.<target>.*.yaml` layers.

See `skill/SKILL.md` § CLI Invocation for full resolution rules and examples.
