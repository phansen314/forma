# Satellite Document Architecture

## Concept

The data model system uses a hub-and-spoke document architecture. The hub (`model.forma`) describes what the data *is* — pure shape. Satellite documents describe how the data is *used*, *validated*, or *represented* in specific contexts.

```
model.forma               ← Hub: structure, shapes, references (.forma recommended)
├── model.validate.yaml   ← Spoke: validation rules
├── model.kotlin.yaml     ← Spoke: Kotlin generation profile
├── model.typescript.yaml ← Spoke: TypeScript generation profile
├── model.sql.yaml        ← Spoke: SQL generation profile
└── model.kotlin.api.yaml ← Spoke: Kotlin API layer overrides
```

Satellites are always `.yaml`.

## Core Rules

1. **Satellites reference the hub by name.** They use shape names, field names, and choice names from the hub. They never redefine structural elements.

2. **Satellites are independently optional.** The hub is self-contained. Any satellite can be absent without invalidating the model. Code generation without a target profile uses defaults.

3. **Satellites can stack.** A base Kotlin profile might set global immutability and collection strategy. A Kotlin API profile layers on serialization annotations and derived DTOs. The agent merges them in order.

4. **The hub never grows for satellite concerns.** If a feature is target-specific, validation-specific, or deployment-specific, it goes in a satellite. The hub stays small.

5. **Hub namespace serves as default package.** If the hub declares `(namespace com.example.foo)`, generators use it as the default package/module. Satellites can override via the generator's `package:` setting.

6. **Constraints belong in satellites.** Primary keys, unique constraints, default values, and relationship cardinality details are satellite concerns — they describe how data is *stored* or *used*, not what it *is*.

## Satellite Categories

### Target Profiles (`model.{target}.yaml`)

Control how the hub maps to a specific language or persistence layer.

**Sections a target profile may include:**

| Section | Purpose | Example |
|---|---|---|
| `generators` | Named output contexts — package, immutability, collections, serialization | `model: { package: com.example.model }` |
| `type_mappings` | Primitive → target type | `UUID: java.util.UUID` |
| `emitters` | Per-generator concept mapping — default styles and per-name overrides for shapes, choices, atoms | `model: { default: { shape: data_class } }` |
| `derived_types` | DTOs derived from shapes | `BirdCreate: { from: Bird, omit: [id] }` |
| `relationships` | FK naming, join table strategy | `fk_pattern: "{type}_id"` |
| `interfaces` | Generated interfaces shapes can implement | `Identifiable: { properties: { id: UUID } }` |

### Validation Profiles (`model.validate.yaml`)

Define behavioral rules that reference the hub's shapes. Rules are organized into named contexts — each context is a self-contained rule set for a specific use case.

```yaml
validations:
  <context-name>:
    extends: <other-context>     # optional — inherit rules from another context
    default:                      # optional — per-atom-type fallback rules
      <atom-type>:
        - <rule>
    <ShapeName>:
      <field>:
        - <rule>
```

**Reserved keys** within a context: `extends:` and `default:`. Everything else is a shape name.

**`default:`** provides per-atom-type fallback rules. Fields with explicit rules override their type's default.

**`extends:`** inherits rules from another context. Child rules override at field granularity — if the child defines rules for `User.email`, they replace the parent's entirely. Unmentioned fields keep the parent's rules.

```yaml
validations:
  base:
    default:
      string:
        - max_length: 10000
      datetime:
        - immutable
    User:
      email:
        - format: email
      username:
        - min_length: 3
        - max_length: 50

  api:
    extends: base
    default:
      string:
        - max_length: 50000       # relax for API input

  persistence:
    extends: base
    default:
      string:
        - max_length: 255         # tighten for DB columns
    User:
      email:
        - max_length: 320         # override base's email rules
```

The target profile controls *how* validation rules become code. The validation satellite says *what* constraints exist:

```yaml
# In model.kotlin.yaml
generators:
  model:
    validation:
      library: jakarta-validation
      context: api                # which validation context to apply
```

### Layer Profiles (`model.{target}.{layer}.yaml`)

Override a base target profile for a specific application layer.

```yaml
# model.kotlin.api.yaml — overrides model.kotlin.yaml for API layer

layer: api

generators:
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
| Generate Kotlin | Hub + `profiles/kotlin/*.yaml` + `model.kotlin.yaml` |
| Generate Kotlin API DTOs | Hub + `profiles/kotlin/*.yaml` + `model.kotlin.yaml` + `model.kotlin.api.yaml` |
| Add validation | Hub + `model.validate.yaml` |
| Generate SQL DDL | Hub + `profiles/sql/*.yaml` + `model.sql.yaml` |
| Validate atom coverage | Hub + satellite stack (same as generation) — check, don't generate |

### Merge Order

When multiple satellites apply, they merge in specificity order:

1. **Hub** (`model.forma`) — structural truth
2. **Base profile** (`profiles/<target>/*.yaml`) — universal type mappings and collection defaults for the target language
3. **Convention satellite** (`model.<target>.yaml`) — model-specific target profile discovered by naming convention
4. **Explicit satellites** — additional satellite files provided directly (e.g., via CLI arguments)
5. **Layer profiles** (`model.<target>.*.yaml`) — layer-specific overrides (API, persistence, etc.)

Base profiles provide universal mappings that apply to any model targeting that language — primitive type mappings, standard collection defaults, and common library imports. Model-specific satellites layer on top with generator settings, emitter overrides, and derived types.

Later documents override earlier ones for conflicting keys. Non-conflicting keys accumulate.

### Creating New Satellites

When a user needs a new satellite type, follow this pattern:

1. Identify what concern the satellite addresses (target, validation, deployment, etc.)
2. Choose a naming convention consistent with existing satellites
3. Structure the satellite to reference hub elements by name
4. Document what each section controls and what the defaults are
5. Include an example showing the satellite in action alongside the hub

### Base Profiles

The `profiles/<target>/` directory contains base satellite files that provide universal mappings for a target language. These are loaded automatically before model-specific satellites.

**What base profiles contain:**
- `type_mappings` — primitive atom → target type (e.g., `UUID: java.util.UUID`)
- Default collection and association types (e.g., `collection: List`)

**What base profiles do NOT contain:**
- Generator `package:` — model-specific, belongs in the model's satellite
- Emitter overrides — model-specific
- `derived_types` / `relationships` — model-specific

Base profiles are designed to be shared across all models targeting the same language. Use `--no-base` (in CLI invocation) to skip loading them when a model's satellite is fully self-contained.
