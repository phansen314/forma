# Satellite Document Architecture

## Concept

The data model system uses a hub-and-satellite document architecture. The hub (`model.forma`) describes what the data *is* — pure shape. Satellite documents describe how the data is *used* or *represented* in specific contexts.

```
model.forma               ← Hub: structure, shapes, references (.forma recommended)
├── model.kotlin.yaml     ← Satellite: Kotlin generation profile
├── model.typescript.yaml ← Satellite: TypeScript generation profile
├── model.sql.yaml        ← Satellite: SQL generation profile
└── model.kotlin.api.yaml ← Satellite: Kotlin API layer overrides
```

Satellites are always `.yaml`.

## Core Rules

1. **Satellites reference the hub by name.** They use shape names, field names, and choice names from the hub. They never redefine structural elements.

2. **Satellites are independently optional.** The hub is self-contained. Any satellite can be absent without invalidating the model. Code generation without a target profile uses defaults.

3. **Satellites can stack.** A base Kotlin profile might set global immutability and collection strategy. A Kotlin API profile layers on serialization annotations and derived DTOs. The agent merges them in order.

4. **The hub never grows for satellite concerns.** If a feature is target-specific or deployment-specific, it goes in a satellite. The hub stays small.

5. **Hub namespace serves as default package.** If the hub declares `(namespace com.example.foo)`, generators use it as the default package/module. Satellites can override via the emitter's `package:` setting.

6. **Constraints belong in satellites.** Primary keys, unique constraints, default values, and relationship cardinality details are satellite concerns — they describe how data is *stored* or *used*, not what it *is*.

## Satellite Categories

### Target Profiles (`model.{target}.yaml`)

Control how the hub maps to a specific language or persistence layer.

**Sections a target profile may include:**

| Section | Purpose | Example |
|---|---|---|
| `type_mappings` | Primitive → target type | `UUID: java.util.UUID` |
| `emitters` | Named output contexts — generation settings (package, immutability, collections, serialization) and concept mapping (`shape:` and `choice:` keys for default styles + per-name overrides). Contains a reserved `atoms:` sub-section for domain atom → base type mappings shared across all emitters. | `atoms: { BirdId: UUID }`, `model: { package: com.example.model, shape: data_class, choice: enum_class }` |
| `derived_types` | DTOs derived from shapes | `BirdCreate: { from: Bird, omit: [id] }` |
| `relationships` | FK naming, join table strategy | `fk_pattern: "{type}_id"` |
| `interfaces` | Generated interfaces shapes can implement | `Identifiable: { properties: { id: UUID } }` |

### Layer Profiles (`model.{target}.{layer}.yaml`)

Override a base target profile for a specific application layer.

```yaml
# model.kotlin.api.yaml — overrides model.kotlin.yaml for API layer

layer: api

emitters:
  model:
    nullability: lenient           # all fields nullable for partial updates
    serialization: kotlinx-serialization

derived_types:
  BirdCreate:
    from: Bird
    omit: [id, created_at, updated_at]

  BirdPatch:
    from: Bird
    partial: true
    omit: [id]

  BirdSummary:
    from: Bird
    pick: [id, name, status]
```

## How the Agent Uses Satellites

### Loading Strategy

The agent loads documents based on the task:

| Task | Documents loaded |
|---|---|
| Review model | Hub only |
| Generate Kotlin | Hub + `model.kotlin.yaml` |
| Generate Kotlin API DTOs | Hub + `model.kotlin.yaml` + `model.kotlin.api.yaml` |
| Generate SQL DDL | Hub + `model.sql.yaml` |
| Validate atom coverage | Hub + satellite stack (same as generation) — check, don't generate |

### Merge Order

When multiple satellites apply, they merge in specificity order:

1. **Hub** (`model.forma`) — structural truth
2. **Convention satellite** (`model.<target>.yaml`) — model-specific target profile discovered by naming convention
3. **Explicit satellites** — additional satellite files provided directly (e.g., via CLI arguments)
4. **Layer profiles** (`model.<target>.*.yaml`) — layer-specific overrides (API, persistence, etc.)

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

### Creating New Satellites

When a user needs a new satellite type, follow this pattern:

1. Identify what concern the satellite addresses (target, deployment, etc.)
2. Choose a naming convention consistent with existing satellites
3. Structure the satellite to reference hub elements by name
4. Document what each section controls and what the defaults are
5. Include an example showing the satellite in action alongside the hub

