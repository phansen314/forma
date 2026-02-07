# Data Model Format — Quick Reference

## Primitives

`string` `text` `int` `float` `bool` `datetime` `date` `UUID` `json`

## Nullability

Append `?` to any type. Non-null by default.

```yaml
name: string          # required
bio: text?            # nullable
```

## Collections

```yaml
tags: list(string)        # ordered
unique_tags: set(string)  # unique
metadata: map(string, json)
items: list(string)?      # nullable list
```

Custom wrappers allowed — defined in target profiles: `plist(T)`, `tree(T)`, etc.

## Field Syntax

```yaml
# Simple — no constraints:
name: string
location: Location?

# Constrained — type + constraints as list:
id: [UUID, primary_key]
email: [Email, unique]
count: [int, default: 1]
```

Constraints: `primary_key`, `unique`, `default: <value>`

## Type System — Six Concepts

```yaml
# 1. Composite types — named field groups, used as types
composite_types:
  Location:
    latitude: float
    longitude: float

# 2. Unions — discriminated sum types
unions:
  Payment:
    common:               # optional shared fields
      amount: float
    CreditCard:
      number: string
    BankTransfer:
      account: string

# 3. Enums — fixed value sets
enums:
  Status: [active, archived, deleted]

# 4. Type aliases — semantic names
type_aliases:
  UserId: UUID
  Email: string

# 5. Mixins — shared field templates (NOT types)
mixins:
  Timestamped:
    created_at: datetime
    updated_at: datetime?

# 6. Entities — domain objects with identity
entities:
  User:
    use: [Timestamped]        # pull in mixin fields
    fields:
      id: [UserId, primary_key]
      email: [Email, unique]
    relationships:
      posts: { target: Post, cardinality: one_to_many }
```

## Relationships

```yaml
relationships:
  posts: { target: Post, cardinality: one_to_many }
  author: { target: User, cardinality: many_to_one }
  tags: { target: Tag, cardinality: many_to_many }
  profile: { target: Profile, cardinality: one_to_one }
```

FK derivation is a target profile concern, not specified in core model.

## Document Architecture

```
model.yaml              ← Structure (hub)
model.validate.yaml     ← Validation rules (satellite)
model.kotlin.yaml       ← Kotlin target profile (satellite)
model.sql.yaml          ← SQL target profile (satellite)
```
