# CLAUDE.md — Forma

## What is Forma?

A data model definition format. Define the shape of your data once in a `.forma` hub file, then generate code for any target (Kotlin, TypeScript, SQL, etc.) using satellite profile documents.

## Repo Structure

```
spec/SPEC.md                          — Core format specification (source of truth)
skill/SKILL.md                        — Agent skill: task workflows for defining/generating/reviewing models
skill/references/quick-reference.md   — One-page syntax cheat sheet
skill/references/satellite-architecture.md — Hub-and-satellite document pattern
skill/references/kotlin-profile.md    — Kotlin target profile documentation
skill/tools/validate.py               — Bundled hub model validator (Python, .forma only)
skill/tools/forma_parser.py           — .forma DSL parser (Python)
examples/birdtracker.forma            — Complete example model
examples/birdtracker.kotlin.yaml      — Example Kotlin target profile
examples/birdtracker.sql.yaml         — Example SQL target profile
examples/birdtracker.validate.yaml    — Example validation satellite
CHANGELOG.md                          — Version history
CONTRIBUTING.md                       — How to contribute target profiles
```

No code to build or test — this repo is a spec, agent skill, and examples.

## Core Design Principles

- **Structure, not validation.** The hub describes what data *is* (shapes, fields). Behavioral rules (format checks, range constraints, immutability) and structural constraints (primary keys, unique, defaults) belong in satellites.
- **Hub-and-satellite architecture.** `model.forma` is the hub (pure shape). Satellites (`model.validate.yaml`, `model.kotlin.yaml`, etc.) add target-specific or behavioral context. Satellites reference the hub by name, never redefine structure. The hub never grows for satellite concerns.
- **Non-null by default.** Append `?` to opt into nullable. No `required` keyword.
- **Mixins over inheritance.** Shared fields use `mixins` + `[MixinName]`, not class inheritance. Mixins are field templates with optional composition, not standalone types.
- **Structural primitives over behavioral wrappers.** `[T]` (collection) and `{K, V}` (association) describe shape without implying ordering, uniqueness, or lookup behavior. Target profiles decide the concrete type.
- **Angle brackets for generics.** All type parameterization uses `<>`: `tree<T>`, `result<Bird, Error>`, `Versioned<Bird>`. `[T]` and `{K,V}` are shorthand sugar for `coll<T>` and `dict<K,V>`.
- **References are fields.** `observations: [Observation]` and `bird: Bird` — targets infer cardinality from cross-references. No explicit relationship declarations in the hub.

## Three Core Concepts

| Concept | Purpose | Used as field type? |
|---|---|---|
| Shapes | Named structured types with optional mixin fields | Yes |
| Choices | Discriminated alternatives — enum-like (all bare) or union-like (fielded) | Yes |
| Mixins | Shared field templates with optional composition | No — inlined into shapes |

**Atoms**: Any name not declared as a shape, choice, or mixin is an atom. Atoms are valid — target profiles map them. Primitive atoms (`string`, `UUID`) resolve via `type_mappings`. Domain atoms (`BirdId`, `Email`) resolve via `emitters.atoms` to a base type, then through `type_mappings`. Per-name style overrides in emitters control representation (value class, typealias, etc.).

## Field Syntax

Every field is `name: type` or `name: type?`. Nothing else in the hub.

```forma
name: string                    // simple
id: UUID                        // no constraints in hub
bio: text?                      // nullable
tags: [string]                  // collection
metadata: {string, json}?       // nullable association
observations: [Observation]     // reference (target infers cardinality)
```

Constraints (`primary_key`, `unique`, `default`) are satellite concerns.

## `.forma` Syntax

Every declaration is a parenthesized form. Singular forms define one item; plural forms group multiple items.

**Namespace (optional):** `(namespace com.example.foo)` — at most one per file, stored in `meta.namespace`. Generators use it as default package when the satellite's emitter doesn't override via `package:`.

**Singular:** `(model ...)`, `(mixin ...)`, `(choice ...)`, `(shape ...)`

**Plural:** `(mixins (Name field ...) ...)`, `(choices (Name variant ...) ...)`, `(shapes (Name field ...) ...)`

Singular and plural forms can be mixed freely in the same file.

## Document Naming Convention

```
model.forma                — Hub: structure
model.validate.yaml        — Validation rules
model.{target}.yaml        — Target profile (e.g., model.kotlin.yaml)
model.{target}.{layer}.yaml — Layer override (e.g., model.kotlin.api.yaml)
```

**CLI invocation**: `/forma model.forma --<target> [satellite-files...]` — see `skill/SKILL.md`.

## Naming Conventions

- Shapes, choices, mixins: `PascalCase`
- Fields, choice variants: `snake_case`
- Mixins: descriptive adjectives (`Timestamped`, `SoftDeletable`, `Auditable`)

## Key Decision Boundaries

When deciding where something belongs, ask: "Does this describe what the data *is*, or how it's *used*?"

- Shape/structure → hub (`model.forma`)
- Primary keys, unique constraints, defaults → target profile satellite
- Validation rules (format, range, immutability) → `model.validate.yaml` (named contexts)
- Which validation context to apply → target profile (`emitters.<name>.validation.context`)
- Validation library/annotations → target profile (`emitters.<name>.validation.library`)
- Type mappings, collection strategies, serialization, FK naming → target profile
- Derived types (DTOs like `BirdCreate`, `BirdPatch`) → target layer profile
- Whether a shape is a table, embedded value, etc. → target profile
