# Forma

A YAML-based format for defining data models. Describe the shape of your data once, generate code for any target.

## What is Forma?

Forma is a language-agnostic data model definition format designed for agent-assisted code generation. You write a single `model.yaml` describing your types, entities, and relationships. Target profiles tell the generator how to express that structure in Kotlin, TypeScript, SQL, or anything else.

```yaml
composite_types:
  Location:
    latitude: float
    longitude: float

enums:
  Status: [active, archived, deleted]

entities:
  User:
    use: [Timestamped]
    fields:
      id: [UUID, primary_key]
      name: string
      email: [Email, unique]
      status: Status
      location: Location?
    relationships:
      posts: { target: Post, cardinality: one_to_many }
```

## Design Philosophy

**Structure, not validation.** The core spec describes what data *is* — types, fields, relationships. How it's validated, serialized, or stored is handled by satellite documents.

**Minimal boilerplate.** Non-null by default (`?` opts in to nullable). Simple fields are just `name: type`. List syntax only when you need constraints.

**Hub and satellites.** One structural model, many target-specific profiles:

```
model.yaml              ← What the data is (hub)
model.validate.yaml     ← How it's validated (satellite)
model.kotlin.yaml       ← How it maps to Kotlin (satellite)
model.sql.yaml          ← How it maps to SQL (satellite)
```

## Type System

Six concepts for describing data shape:

| Concept | Purpose | Example |
|---|---|---|
| **Composite types** | Named field groups | `Location { lat, lng }` |
| **Unions** | One of several variants | `Payment = Card \| Bank \| Crypto` |
| **Enums** | Fixed value sets | `Status: [active, deleted]` |
| **Type aliases** | Semantic names | `UserId: UUID` |
| **Mixins** | Shared field templates | `Timestamped { created_at, updated_at }` |
| **Entities** | Domain objects with identity | `User { id, name, email }` |

## Quick Start

### 1. Define your model

Create a `model.yaml`:

```yaml
meta:
  name: MyApp
  version: "1.0"

type_aliases:
  UserId: UUID

mixins:
  Timestamped:
    created_at: datetime
    updated_at: datetime?

entities:
  User:
    use: [Timestamped]
    fields:
      id: [UserId, primary_key]
      name: string
      email: [string, unique]
```

### 2. Add a target profile (optional)

Create a `model.kotlin.yaml`:

```yaml
target: kotlin

globals:
  package: com.example.myapp.model
  immutability: full
  serialization: kotlinx-serialization

type_mappings:
  UUID: java.util.UUID
  datetime: kotlinx.datetime.Instant
```

### 3. Generate

Give both files to an agent with the Forma skill. It reads the model + profile and produces idiomatic code for your target.

## Repo Structure

```
forma/
├── spec/
│   └── SPEC.md                      # Core format specification
├── skill/
│   ├── SKILL.md                     # Agent skill — task workflows
│   └── references/
│       ├── quick-reference.md       # One-page syntax cheat sheet
│       ├── satellite-architecture.md
│       └── kotlin-profile.md        # Example target profile docs
├── examples/
│   ├── birdtracker.yaml             # Complete example model
│   └── birdtracker.kotlin.yaml      # Example Kotlin target profile
└── profiles/
    └── (community target profiles)
```

### Key Files

- **[`spec/SPEC.md`](spec/SPEC.md)** — The full format specification. Read this to understand every feature.
- **[`skill/SKILL.md`](skill/SKILL.md)** — Agent instructions. Drop the `skill/` directory into your agent's skill path.
- **[`examples/birdtracker.yaml`](examples/birdtracker.yaml)** — Annotated example using all features.

## Features

- **Nullability**: `name: string` (required) vs `bio: text?` (nullable)
- **Two field forms**: `name: string` (simple) or `id: [UUID, primary_key]` (constrained)
- **Composite types**: Named field groups used as types
- **Unions**: Discriminated sum types with optional shared fields
- **Enums**: Inline `[a, b, c]` or expanded list syntax
- **Mixins**: `use: [Timestamped, Auditable]` — shared fields without inheritance
- **Collections**: `list(T)`, `set(T)`, `map(K,V)` + custom wrappers via target profiles
- **Relationships**: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`
- **FK derivation**: Relationships are structural; FK column names are a target profile concern
- **Satellite architecture**: Validation, target profiles, and layer overrides in separate files

## Using the Agent Skill

Copy the `skill/` directory into your agent's skill path. The skill triggers on data modeling tasks — defining entities, generating code, reviewing models, creating target profiles.

The agent reads `SPEC.md` for format details and `SKILL.md` for task workflows. Reference docs in `skill/references/` provide the satellite architecture guide, a syntax cheat sheet, and an example Kotlin profile.

## License

MIT
