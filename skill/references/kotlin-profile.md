# Kotlin Target Profile Spec

## Overview

A satellite document that provides Kotlin-specific generation directives. The agent reads this alongside the core structural spec (`model.forma`) when generating Kotlin code.

This file does **not** redefine structure. It tells the generator **how** to express that structure in Kotlin.

---

## Format

```yaml
target: kotlin

# ──────────────────────────────────────
# Generators — named output contexts
# ──────────────────────────────────────
generators:
  model:
    package: com.example.birdtracker.model   # overrides hub (namespace ...) if set

    immutability: full
    # full   → val-only properties, immutable collections, copy-on-write
    # partial → val properties, stdlib mutable collections
    # none    → var properties, mutable collections

    nullability: strict
    # strict → mirrors the ? from core spec exactly
    # lenient → all fields nullable (e.g., for partial/patch DTOs)

    collections:
      library: kotlinx-immutable
      # kotlinx-immutable → kotlinx.collections.immutable (PersistentList, PersistentSet, PersistentMap)
      # stdlib            → kotlin.collections (List, Set, Map — already read-only interfaces)

      # How structural primitives from core spec map to Kotlin types:
      collection: PersistentList          # [T] (= coll<T>) → PersistentList<T>
      association: PersistentMap          # {K, V} (= dict<K, V>) → PersistentMap<K, V>

      custom_wrappers:
        tree: com.example.collections.Tree

    serialization: kotlinx-serialization
    # kotlinx-serialization → @Serializable + json config
    # jackson               → @JsonProperty annotations
    # moshi                 → @Json annotations
    # none                  → no serialization annotations

    validation:
      library: jakarta-validation
      # jakarta-validation → Jakarta Bean Validation annotations (@NotNull, @Size, @Email, etc.)
      # none               → no validation annotations (default)
      context: base
      # Which named validation context from model.validate.yaml to apply.
      # Omit to skip validation annotation generation.

# ──────────────────────────────────────
# Type mappings (override/extend base)
# ──────────────────────────────────────
type_mappings:
  UUID: java.util.UUID
  string: String
  text: String
  int: Int
  float: Double
  bool: Boolean
  datetime: kotlinx.datetime.Instant
  date: kotlinx.datetime.LocalDate
  json: kotlinx.serialization.json.JsonElement

# ──────────────────────────────────────
# Emitters — per-generator concept mapping
# ──────────────────────────────────────
emitters:
  model:
    default:
      shape: data_class
      # data_class → data class (equals, hashCode, copy, destructuring)
      # value_class → @JvmInline value class (single-field types only)
      # class      → regular class
      # interface  → interface (for multi-platform expect/actual)
      # bitmask    → @JvmInline value class packing fields into Int/Long
      choice: enum_class
      # enum_class       → standard enum class (for all-bare choices)
      # bitmask          → Int-backed bitmask for combinable flags
      # sealed_class     → sealed class with data class variants (for fielded choices)
      # sealed_interface → sealed interface (for multi-inheritance)
      atom: typealias
      # typealias   → Kotlin typealias (transparent, no runtime overhead)
      # value_class → @JvmInline value class (type-safe wrapper, zero allocation)
      # class       → regular class wrapper

    # Per-name overrides — generator infers concept type from hub
    Bird:
      annotations: ["@Serializable"]
      implements: [Identifiable]
    Observation:
      annotations: ["@Serializable"]

    Habitat:
      style: bitmask
      # Habitat becomes a bitmask because a bird can inhabit multiple habitats.
      # Generates:
      #   @JvmInline
      #   value class HabitatFlags(val bits: Int) {
      #     operator fun contains(flag: HabitatFlags) = bits and flag.bits == flag.bits
      #     operator fun plus(other: HabitatFlags) = HabitatFlags(bits or other.bits)
      #     operator fun minus(other: HabitatFlags) = HabitatFlags(bits and other.bits.inv())
      #     companion object {
      #       val FOREST    = HabitatFlags(1 shl 0)
      #       val WETLAND   = HabitatFlags(1 shl 1)
      #       val GRASSLAND = HabitatFlags(1 shl 2)
      #       val COASTAL   = HabitatFlags(1 shl 3)
      #       val URBAN     = HabitatFlags(1 shl 4)
      #       val NONE      = HabitatFlags(0)
      #       val ALL       = HabitatFlags((1 shl 5) - 1)
      #     }
      #   }
      #
      # The core spec's [Habitat] field collapses to a single HabitatFlags

    BirdId:
      style: value_class
    UserId:
      style: value_class
    # BirdId and UserId become @JvmInline value class wrappers for UUID.
    # Email uses the default typealias.

# ──────────────────────────────────────
# Interfaces to generate
# ──────────────────────────────────────
interfaces:
  Identifiable:
    properties:
      id: UUID
    # Shapes implementing this get `: Identifiable` in their declaration.
    # The generator verifies the shape has a matching `id` field.
```

---

## Generated Output Example

Given the core spec and this Kotlin profile, the agent generates:

```kotlin
package com.example.birdtracker.model

import kotlinx.collections.immutable.PersistentList
import kotlinx.datetime.Instant
import kotlinx.serialization.Serializable
import java.util.UUID

// From shapes (value shapes — no key designation in satellite)
data class ScientificName(
    val common: String,
    val scientific: String,
)

data class Location(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double?,
)

// From choices (fielded) → sealed class with common fields as abstract properties
@Serializable
sealed class MediaAttachment {
    abstract val url: String
    abstract val caption: String?

    data class Photo(
        override val url: String,
        override val caption: String?,
        val width: Int,
        val height: Int,
    ) : MediaAttachment()

    data class Audio(
        override val url: String,
        override val caption: String?,
        val durationSeconds: Double,
        val format: String,
    ) : MediaAttachment()
}

// From choices (all-bare, bitmask override for Habitat)
@JvmInline
value class HabitatFlags(val bits: Int) {
    operator fun contains(flag: HabitatFlags) = bits and flag.bits == flag.bits
    operator fun plus(other: HabitatFlags) = HabitatFlags(bits or other.bits)
    operator fun minus(other: HabitatFlags) = HabitatFlags(bits and other.bits.inv())

    companion object {
        val FOREST    = HabitatFlags(1 shl 0)
        val WETLAND   = HabitatFlags(1 shl 1)
        val GRASSLAND = HabitatFlags(1 shl 2)
        val COASTAL   = HabitatFlags(1 shl 3)
        val URBAN     = HabitatFlags(1 shl 4)
        val NONE      = HabitatFlags(0)
        val ALL       = HabitatFlags((1 shl 5) - 1)
    }
}

// From choices (all-bare) → standard enum
enum class ConservationStatus {
    LEAST_CONCERN,
    VULNERABLE,
    ENDANGERED,
    CRITICAL,
    EXTINCT,
}

// From shapes (identity shapes — satellite designates key + persistence)
@Serializable
data class Bird(
    val id: UUID,
    val name: ScientificName,
    val status: ConservationStatus,
    val habitats: HabitatFlags,
    val description: String?,
    val wingspanCm: Double?,
    val photoUrl: String?,
    val createdAt: Instant,              // from Timestamped mixin
    val updatedAt: Instant?,             // from Timestamped mixin
) : Identifiable

// Shape with choice-typed field
@Serializable
data class Observation(
    val id: UUID,
    val timestamp: Instant,
    val location: Location?,
    val notes: String?,
    val count: Int = 1,
    val media: MediaAttachment?,         // choice type — Photo or Audio
    val createdAt: Instant,              // from Timestamped mixin
    val updatedAt: Instant?,             // from Timestamped mixin
)
```

---

## Design Notes

**Generators and emitters**: The satellite separates *where* code goes (`generators:`) from *what* each concept becomes (`emitters:`). A single hub shape can appear in multiple generators — e.g., a bitmask for the game engine and a DTO for the API layer. Each generator entry under `emitters:` has a `default:` block for fallback styles and per-name overrides. The generator infers the concept type (shape, choice, or atom) from the hub, so overrides don't need to declare which section they belong to.

**Bitmask generation**: When a choice is marked `style: bitmask`, the generator produces a `@JvmInline value class` wrapping an `Int`. This gives type safety (can't accidentally pass a raw `Int` where `HabitatFlags` is expected) with zero runtime allocation overhead — the JVM sees a plain `int` at the call site. Any `[E]` field referencing a bitmask choice collapses to a single value class field. The generator also produces `contains`, `plus`, `minus` operators and `NONE`/`ALL` constants.

**Choice → sealed class**: Fielded choices are a natural fit for Kotlin's sealed class hierarchies. Common fields become `abstract` properties on the sealed parent, ensuring the compiler enforces them on every variant. `when` expressions over a sealed class are exhaustive — the compiler catches missing variants. The `sealed_interface` option is available when variants need to implement multiple interfaces.

**Immutability strategy**: `full` immutability means the generated code is safe to share across coroutines without copying — `PersistentList` from kotlinx.collections.immutable gives structural sharing out of the box. The `partial` option uses Kotlin's read-only `List` interface (which doesn't guarantee the underlying implementation is immutable).

---

## Bitmask Shapes

When a shape override uses `style: bitmask`, the generator packs all fields into a single `Int` (≤32 total bits) or `Long` (≤64 total bits). The backing class and mutation API depend on the `mutation:` option.

### Satellite syntax

```yaml
emitters:
  engine:
    BirdState:
      style: bitmask
      mutation: copy_on_write
      # copy_on_write → @JvmInline value class, withX() methods return new instances (default)
      # in_place      → class with var bits, setX() methods mutate in place
      bits:
        id: 10
        tucked_count: 6
        eggs: 4
        cached_food: 6 per enum
        position: 3
```

`style: bitmask` implies all of:
- `EMPTY` companion constant (all bits zero)
- `create()` factory with defaults
- Typed getters for every field
- Mutation API determined by `mutation:` (default `copy_on_write`)

### `bits:` section

Each entry is `field_name: width` where width is an integer number of bits. Three forms:

| Form | Meaning |
|---|---|
| `field: N` | Field occupies N bits. Getter returns `Int` (or the mapped atom type). |
| `field: N per enum` | Association field. N bits **per variant** of the key enum (excluding wildcards like `wild`). Hub declares the association type (e.g., `{Food, int}`), so the enum name is already known. |
| `field: N of enum` | Fixed-capacity array. N elements of the field's choice type. Bits per element = `ceil(log2(variant_count + 1))` (+1 reserves a sentinel for empty slots). Hub declares the collection type (e.g., `[DiceFace]`). |

### Auto-inference of choice-typed fields

Fields whose hub type is an all-bare choice (enum-like) can be **omitted** from `bits:`. The generator infers the bit width as `ceil(log2(variant_count))`.

Example: `lives_in: Habitat` in the hub, where `Habitat` has 3 variants (`forest`, `grassland`, `wetland`) → `ceil(log2(3))` = 2 bits. No entry needed in `bits:`.

Fields with non-choice types (int, atoms, associations) must always be listed explicitly.

### Backing type selection

The generator sums all bit widths (including auto-inferred fields and per-enum expansions) and selects the smallest primitive:

| Total bits | Backing type |
|---|---|
| ≤ 32 | `Int` |
| ≤ 64 | `Long` |
| > 64 | Error — shape cannot be packed into a single primitive |

### Generated API

Common to both mutation modes:

- **Getters** — `val fieldName: Type` properties using bit shifts and masks
- **`EMPTY`** — companion constant with all bits zero
- **`create()`** — companion factory taking all fields (choice-typed fields required, others defaulted to 0)

#### `mutation: copy_on_write` (default)

Backing: `@JvmInline value class` wrapping `Int` or `Long`. Zero allocation overhead — the JVM sees a plain primitive.

- **`withX()` methods** — `fun withFieldName(value: Type): ShapeName` returning a new instance with that field updated
- **Per-enum fields** (`N per enum`) — `fun cachedFood(food: Food): Int` accessor, `val totalCachedFood: Int` aggregate; `fun withCachedFood(food: Food, count: Int): ShapeName` returns new instance
- **Array-of-enum fields** (`N of enum`) — `val slots: List<DiceFace>` getter, `val slotCount: Int`; `fun withSlot(index: Int, value: DiceFace?): ShapeName` returns new instance

#### `mutation: in_place`

Backing: `class` with `var bits: Int` (or `Long`). Allows true in-place mutation at the cost of heap allocation.

- **`setX()` methods** — `fun setFieldName(value: Type)` mutates the backing bits directly
- **Per-enum fields** (`N per enum`) — `fun cachedFood(food: Food): Int` accessor, `val totalCachedFood: Int` aggregate; `fun setCachedFood(food: Food, count: Int)` mutates in place
- **Array-of-enum fields** (`N of enum`) — `val slots: List<DiceFace>` getter, `val slotCount: Int`; `fun setSlot(index: Int, value: DiceFace?)` mutates in place

---

**Profile inheritance**: A project might have a base Kotlin profile and override it per module:

```
model.kotlin.yaml           ← base: kotlinx-immutable, full immutability
model.kotlin.api.yaml       ← API layer: adds @Serializable, lenient nullability for DTOs
model.kotlin.domain.yaml    ← Domain layer: sealed classes for choices, stricter types
```
