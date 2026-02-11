# Kotlin Target Profile Spec

## Overview

A satellite document that provides Kotlin-specific generation directives. The agent reads this alongside the core structural spec (`model.forma`) when generating Kotlin code.

This file does **not** redefine structure. It tells the generator **how** to express that structure in Kotlin.

---

## Format

```yaml
target: kotlin

# ──────────────────────────────────────
# Global generation defaults
# ──────────────────────────────────────
globals:
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
# Choice directives
# ──────────────────────────────────────
choices:
  default: enum_class
  # enum_class       → standard enum class (for all-bare choices)
  # bitmask          → Int-backed bitmask for combinable flags
  # sealed_class     → sealed class with data class variants (for fielded choices)
  # sealed_interface → sealed interface (for multi-inheritance)

  overrides:
    Habitat: bitmask
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

# ──────────────────────────────────────
# Shape directives
# ──────────────────────────────────────
shapes:
  default:
    style: data_class
    # data_class → data class (equals, hashCode, copy, destructuring)
    # value_class → @JvmInline value class (single-field types only)
    # class      → regular class
    # interface  → interface (for multi-platform expect/actual)

    implements: []
    # Interfaces all generated shapes should implement
    # e.g., [Identifiable, Timestamped]

    annotations: []
    # Annotations applied to all shapes
    # e.g., ["@Serializable"]

  overrides:
    Bird:
      annotations: ["@Serializable"]
      implements: [Identifiable]

    Observation:
      annotations: ["@Serializable"]

# ──────────────────────────────────────
# Atom directives
# ──────────────────────────────────────
atoms:
  default: typealias
  # typealias   → Kotlin typealias (transparent, no runtime overhead)
  # value_class → @JvmInline value class (type-safe wrapper, zero allocation)
  # class       → regular class wrapper

  overrides:
    BirdId: value_class
    UserId: value_class
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

**Why a separate file?** The core spec says `Bird` has a field `habitats: [Habitat]`. That's structurally correct — it's a collection of habitat values. But in Kotlin, the *optimal* representation might be a bitmask integer, or a `PersistentSet<Habitat>`, or an `EnumSet<Habitat>`. That's a generation concern, not a structural one. The `shapes:` section in the satellite profile controls how each shape is represented — value shapes like `Location` and identity shapes like `Bird` can have different strategies via the `overrides` map.

**Bitmask generation**: When a choice is marked `bitmask`, the generator produces a `@JvmInline value class` wrapping an `Int`. This gives type safety (can't accidentally pass a raw `Int` where `HabitatFlags` is expected) with zero runtime allocation overhead — the JVM sees a plain `int` at the call site. Any `[E]` field referencing a bitmask choice collapses to a single value class field. The generator also produces `contains`, `plus`, `minus` operators and `NONE`/`ALL` constants.

**Choice → sealed class**: Fielded choices are a natural fit for Kotlin's sealed class hierarchies. Common fields become `abstract` properties on the sealed parent, ensuring the compiler enforces them on every variant. `when` expressions over a sealed class are exhaustive — the compiler catches missing variants. The `sealed_interface` option is available when variants need to implement multiple interfaces.

**Immutability strategy**: `full` immutability means the generated code is safe to share across coroutines without copying — `PersistentList` from kotlinx.collections.immutable gives structural sharing out of the box. The `partial` option uses Kotlin's read-only `List` interface (which doesn't guarantee the underlying implementation is immutable).

**Unified `shapes:` section**: The satellite profile uses a single `shapes:` section to control all shapes — both value shapes (like `Location`) and identity shapes (like `Bird`). Per-shape overrides select annotations, interfaces, and style. The satellite doesn't need separate sections because satellite-level signals (constraints, persistence strategies, key designations) already distinguish shape roles.

**Profile inheritance**: A project might have a base Kotlin profile and override it per module:

```
model.kotlin.yaml           ← base: kotlinx-immutable, full immutability
model.kotlin.api.yaml       ← API layer: adds @Serializable, lenient nullability for DTOs
model.kotlin.domain.yaml    ← Domain layer: sealed classes for choices, stricter types
```
