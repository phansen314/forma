# Satellite Document Architecture

## Concept

The data model system uses a hub-and-spoke document architecture. The core structural spec (`model.yaml`) is the hub — it describes what the data *is*. Satellite documents describe how the data is *used*, *validated*, or *represented* in specific contexts.

```
model.yaml                ← Hub: structure, types, relationships
├── model.validate.yaml   ← Spoke: validation rules
├── model.kotlin.yaml     ← Spoke: Kotlin generation profile
├── model.typescript.yaml ← Spoke: TypeScript generation profile
├── model.sql.yaml        ← Spoke: SQL generation profile
└── model.kotlin.api.yaml ← Spoke: Kotlin API layer overrides
```

## Core Rules

1. **Satellites reference the hub by name.** They use entity names, field names, type names, and enum names from the core spec. They never redefine structural elements.

2. **Satellites are independently optional.** The core model is self-contained. Any satellite can be absent without invalidating the model. Code generation without a target profile uses defaults.

3. **Satellites can stack.** A base Kotlin profile might set global immutability and collection strategy. A Kotlin API profile layers on serialization annotations and derived DTOs. The agent merges them in order.

4. **The hub never grows for satellite concerns.** If a feature is target-specific, validation-specific, or deployment-specific, it goes in a satellite. The hub stays small.

## Satellite Categories

### Target Profiles (`model.{target}.yaml`)

Control how the core model maps to a specific language or persistence layer.

**Sections a target profile may include:**

| Section | Purpose | Example |
|---|---|---|
| `globals` | Package, immutability, serialization | `package: com.example.model` |
| `type_mappings` | Primitive → target type | `UUID: java.util.UUID` |
| `type_aliases` | Alias representation strategy | `default: value_class` |
| `collection_wrappers` | Collection type mappings + custom wrappers | `list: PersistentList` |
| `composite_types` | How composites are represented | `default: data_class` |
| `unions` | Union representation | `default: sealed_class` |
| `enums` | Enum strategy + per-enum overrides | `Habitat: bitmask` |
| `entities` | Entity style, annotations, interfaces | `Bird: { annotations: ["@Serializable"] }` |
| `derived_types` | DTOs derived from entities | `BirdCreate: { from: Bird, omit: [id] }` |
| `relationships` | FK naming, join table strategy | `fk_pattern: "{entity}_id"` |
| `interfaces` | Generated interfaces entities can implement | `Identifiable: { properties: { id: UUID } }` |

### Validation Profiles (`model.validate.yaml`)

Define behavioral rules that reference the core model's structure.

```yaml
validations:
  User:
    email: [format: email]
    username: [min_length: 3, max_length: 50, pattern: "^[a-z0-9_]+$"]
  
  Bird:
    wingspan_cm: [min: 1, max: 500]
    created_at: [immutable]
  
  Observation:
    count: [min: 1]
    timestamp: [not_future: true]
```

### Layer Profiles (`model.{target}.{layer}.yaml`)

Override a base target profile for a specific application layer.

```yaml
# model.kotlin.api.yaml — overrides model.kotlin.yaml for API layer

layer: api

globals:
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
| Review model | `model.yaml` only |
| Generate Kotlin | `model.yaml` + `model.kotlin.yaml` |
| Generate Kotlin API DTOs | `model.yaml` + `model.kotlin.yaml` + `model.kotlin.api.yaml` |
| Add validation | `model.yaml` + `model.validate.yaml` |
| Generate SQL DDL | `model.yaml` + `model.sql.yaml` |

### Merge Order

When multiple satellites apply, they merge in specificity order:

1. Core model (`model.yaml`) — structural truth
2. Base target profile (`model.kotlin.yaml`) — language defaults
3. Layer profile (`model.kotlin.api.yaml`) — layer-specific overrides

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

### Creating New Satellites

When a user needs a new satellite type, follow this pattern:

1. Identify what concern the satellite addresses (target, validation, deployment, etc.)
2. Choose a naming convention consistent with existing satellites
3. Structure the satellite to reference core model elements by name
4. Document what each section controls and what the defaults are
5. Include an example showing the satellite in action alongside the core model
