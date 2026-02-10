# Data Model Format — Quick Reference

## Hub Formats

`.forma` — S-expression DSL. Satellites are YAML.

## Primitives

`string` `text` `int` `float` `bool` `datetime` `date` `UUID` `json`

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
// Comments use double-slash

(model AppName v1.0 "Description")

// Type aliases — semantic names for base types
(alias UserId UUID)
(alias Email string)

// Mixins — shared field templates (optional type params in <>)
(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

(mixin Versioned<T>
  current: T
  history: [T]
  version: int)

// Enums — fixed value sets (space-separated)
(enum Status active archived deleted)

// Types — structured types with optional mixin inheritance
(type Location
  latitude: float
  longitude: float)

(type User [Timestamped]
  id: UserId
  email: Email
  location: Location?
  posts: [Post])

(type Bird [Versioned<Bird> Timestamped]
  name: string
  species: string)

// Unions — discriminated sum types
(union Payment
  (common
    amount: float)
  (CreditCard
    number: string)
  (BankTransfer
    account: string)
  Cash)                        // fieldless variant (marker)
```

## Plural Forms

Group multiple definitions in a single form. Same IR output as singular forms.

```forma
(aliases
  UserId UUID
  Email string)

(enums
  (Status active archived deleted)
  (Role admin editor viewer))

(mixins
  (Timestamped
    created_at: datetime
    updated_at: datetime?)
  (Versioned<T>
    current: T
    history: [T]
    version: int))

(types
  (Location
    latitude: float
    longitude: float)
  (User [Timestamped]
    id: UserId
    email: Email))

(unions
  (Payment
    (common amount: float)
    (CreditCard number: string)
    Cash))
```

Singular and plural forms can be mixed freely.

## Cardinality Inference

Targets infer cardinality from cross-references:

| Side A | Side B | Cardinality |
|--------|--------|-------------|
| `posts: [Post]` | `author: User` | **1:N** |
| `tags: [Tag]` | `posts: [Post]` | **N:M** |
| `profile: Profile` | `user: User` | **1:1** |

## Document Architecture

```
model.forma              ← Structure (hub)
model.validate.yaml      ← Validation rules (satellite)
model.kotlin.yaml        ← Kotlin target profile (satellite)
model.sql.yaml           ← SQL target profile (satellite)
```
