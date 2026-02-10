# Forma

A data model definition format. Describe the shape of your data once, generate code for any target.

## What is Forma?

Forma is a language-agnostic data model definition format designed for agent-assisted code generation. You write a single `model.forma` describing your types. Target profiles tell the generator how to express that structure in Kotlin, TypeScript, SQL, or anything else.

```forma
(type Location
  latitude: float
  longitude: float)

(type User [Timestamped]
  id: UserId
  name: string
  email: Email
  status: Status
  location: Location?)

(enum Status active archived deleted)
```

## Design Philosophy

**Structure, not validation.** The core spec describes what data *is* — types, fields, references. How it's validated, serialized, or stored is handled by satellite documents.

**Minimal boilerplate.** Non-null by default (`?` opts in to nullable). Every field is just `name: type`. S-expression syntax keeps declarations clean and uniform.

**Hub and satellites.** One structural model, many target-specific profiles:

```
model.forma             ← What the data is (hub)
model.validate.yaml     ← How it's validated (satellite)
model.kotlin.yaml       ← How it maps to Kotlin (satellite)
model.sql.yaml          ← How it maps to SQL (satellite)
```

```mermaid
flowchart LR
    HUB[model.forma] --> GEN[Agent + Generator]
    VAL[model.validate.yaml] -.-> GEN
    TGT[model.kotlin.yaml<br/>model.sql.yaml<br/>...] -.-> GEN
    GEN --> OUT[Kotlin / SQL / TypeScript / ...]
```

## Type System

Five concepts for describing data shape:

| Concept | Purpose | Example |
|---|---|---|
| **Types** | Named structured types | `(type Location latitude: float longitude: float)` |
| **Unions** | One of several variants | `(union Payment (CreditCard ...) (BankTransfer ...) Cash)` |
| **Enums** | Fixed value sets | `(enum Status active archived deleted)` |
| **Type aliases** | Semantic names | `(alias UserId UUID)` |
| **Mixins** | Shared field templates | `(mixin Timestamped created_at: datetime)` |

## Quick Start

### 1. Define your model

Create a `model.forma`:

```forma
(model MyApp v1.0 "My application data model")

(alias UserId UUID)

(mixin Timestamped
  created_at: datetime
  updated_at: datetime?)

(type User [Timestamped]
  id: UserId
  name: string
  email: string)
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
│   └── SPEC.md                         # Core format specification
├── skill/
│   ├── SKILL.md                        # Agent skill — task workflows
│   ├── references/
│   │   ├── quick-reference.md          # One-page syntax cheat sheet
│   │   ├── satellite-architecture.md   # Hub-and-satellite pattern
│   │   └── kotlin-profile.md           # Kotlin target profile docs
│   └── tools/
│       ├── validate.py                 # Hub model validator
│       └── forma_parser.py            # .forma DSL parser
├── examples/
│   ├── birdtracker.forma               # Complete example model
│   ├── birdtracker.kotlin.yaml         # Example Kotlin target profile
│   ├── birdtracker.sql.yaml            # Example SQL target profile
│   └── birdtracker.validate.yaml       # Example validation satellite
├── profiles/
│   └── (community target profiles)
├── CHANGELOG.md                        # Version history
└── CONTRIBUTING.md                     # How to contribute target profiles
```

### Key Files

- **[`spec/SPEC.md`](spec/SPEC.md)** — The full format specification. Read this to understand every feature.
- **[`skill/SKILL.md`](skill/SKILL.md)** — Agent instructions. Drop the `skill/` directory into your agent's skill path.
- **[`examples/birdtracker.forma`](examples/birdtracker.forma)** — Annotated example using all features.

## Features

- **S-expression syntax**: Clean `(keyword name ...body...)` forms — minimal token types
- **Nullability**: `name: string` (required) vs `bio: text?` (nullable)
- **Unified types**: All structured types in a single `types:` section — role determined by structural signals
- **Unions**: Discriminated sum types with optional shared fields
- **Enums**: Space-separated values: `(enum Status active deleted)`
- **Mixins**: `[Timestamped]` — shared fields without inheritance
- **Structural primitives**: `[T]` (collection), `{K, V}` (association) — shorthand for `coll<T>`, `dict<K, V>`
- **Angle-bracket generics**: `tree<T>`, `Versioned<Bird>` — unified type parameterization + named wrappers via target profiles
- **References as fields**: `bird: Bird`, `observations: [Observation]` — targets infer cardinality
- **Satellite architecture**: Validation, target profiles, and layer overrides in separate files

## Using the Agent Skill

Copy the `skill/` directory into your agent's skill path. The skill triggers on data modeling tasks — defining types, generating code, reviewing models, creating target profiles.

The agent reads `SPEC.md` for format details and `SKILL.md` for task workflows. Reference docs in `skill/references/` provide the satellite architecture guide, a syntax cheat sheet, and a Kotlin profile example.

## License

MIT
