# Kotlin Target Profile Spec

## Overview

A satellite document that provides Kotlin-specific generation directives. The agent reads this alongside the core structural spec (`model.yaml`) when generating Kotlin code.

This file does **not** redefine structure. It tells the generator **how** to express that structure in Kotlin.

---

## Format

```yaml
target: kotlin

# ──────────────────────────────────────
# Global generation defaults
# ──────────────────────────────────────
globals:
  package: com.example.birdtracker.model
  
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
    
    # How built-in wrappers from core spec map to Kotlin types:
    list: PersistentList                # or List, MutableList, ImmutableList
    set: PersistentSet                  # or Set, MutableSet, ImmutableSet
    map: PersistentMap                  # or Map, MutableMap, ImmutableMap

    # Custom wrappers — extends the core spec's collection vocabulary:
    custom_wrappers:
      plist: kotlinx.collections.immutable.PersistentList
      pset: kotlinx.collections.immutable.PersistentSet
      pmap: kotlinx.collections.immutable.PersistentMap
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
# Composite type directives
# ──────────────────────────────────────
composite_types:
  default: data_class
  # data_class    → data class with val properties
  # value_class   → @JvmInline value class (single-field composites only)
  # interface     → interface with val properties

  overrides:
    # Single-field composites can use value classes for zero-overhead wrapping
    # (not applicable to current model, but available)

# ──────────────────────────────────────
# Enum directives
# ──────────────────────────────────────
enums:
  default: enum_class
  # enum_class    → standard enum class
  # bitmask       → Int-backed bitmask for combinable flags

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
    # The core spec's list(Habitat) field collapses to a single HabitatFlags

# ──────────────────────────────────────
# Union directives
# ──────────────────────────────────────
unions:
  default: sealed_class
  # sealed_class   → sealed class with data class variants (idiomatic Kotlin)
  # sealed_interface → sealed interface with data class variants (more flexible for multi-inheritance)
  
  # Common fields from the union become abstract properties on the sealed type.
  # Variant-specific fields become properties on each data class variant.
  
  overrides: {}
  # Per-union overrides if needed:
  # MediaAttachment: sealed_interface

# ──────────────────────────────────────
# Entity directives
# ──────────────────────────────────────
entities:
  default:
    style: data_class
    # data_class → data class (equals, hashCode, copy, destructuring)
    # class      → regular class
    # interface  → interface (for multi-platform expect/actual)

    implements: []
    # Interfaces all generated entities should implement
    # e.g., [Identifiable, Timestamped]

    annotations: []
    # Annotations applied to all entities
    # e.g., ["@Serializable"]

  overrides:
    Bird:
      annotations: ["@Serializable"]
      implements: [Identifiable]

    Observation:
      annotations: ["@Serializable"]

# ──────────────────────────────────────
# Interfaces to generate
# ──────────────────────────────────────
interfaces:
  Identifiable:
    properties:
      id: UUID
    # Entities implementing this get `: Identifiable` in their declaration.
    # The generator verifies the entity has a matching `id` field.
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

// From composite_types
data class ScientificName(
    val common: String,
    val scientific: String,
)

data class Location(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double?,
)

// From unions → sealed class with common fields as abstract properties
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

// From enums (bitmask override for Habitat)
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

// Standard enum
enum class ConservationStatus {
    LEAST_CONCERN,
    VULNERABLE,
    ENDANGERED,
    CRITICAL,
    EXTINCT,
}

// Entity (uses Timestamped mixin — createdAt, updatedAt)
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

// Entity with union-typed field
@Serializable
data class Observation(
    val id: UUID,
    val timestamp: Instant,
    val location: Location?,
    val notes: String?,
    val count: Int = 1,
    val media: MediaAttachment?,         // union type — Photo or Audio
    val createdAt: Instant,              // from Timestamped mixin
    val updatedAt: Instant?,             // from Timestamped mixin
)
```

---

## Design Notes

**Why a separate file?** The core spec says `Bird` has a field `habitats: list(Habitat)`. That's structurally correct — it's a collection of habitat values. But in Kotlin, the *optimal* representation might be a bitmask integer, or a `PersistentSet<Habitat>`, or an `EnumSet<Habitat>`. That's a generation concern, not a structural one.

**Bitmask generation**: When an enum is marked `bitmask`, the generator produces a `@JvmInline value class` wrapping an `Int`. This gives type safety (can't accidentally pass a raw `Int` where `HabitatFlags` is expected) with zero runtime allocation overhead — the JVM sees a plain `int` at the call site. Any `list(E)` or `set(E)` field referencing a bitmask enum collapses to a single value class field. The generator also produces `contains`, `plus`, `minus` operators and `NONE`/`ALL` constants.

**Union → sealed class**: Unions are a natural fit for Kotlin's sealed class hierarchies. Common fields become `abstract` properties on the sealed parent, ensuring the compiler enforces them on every variant. `when` expressions over a sealed class are exhaustive — the compiler catches missing variants. The `sealed_interface` option is available when variants need to implement multiple interfaces.

**Immutability strategy**: `full` immutability means the generated code is safe to share across coroutines without copying — `PersistentList` from kotlinx.collections.immutable gives structural sharing out of the box. The `partial` option uses Kotlin's read-only `List` interface (which doesn't guarantee the underlying implementation is immutable).

**Profile inheritance**: A project might have a base Kotlin profile and override it per module:

```
model.kotlin.yaml           ← base: kotlinx-immutable, full immutability
model.kotlin.api.yaml       ← API layer: adds @Serializable, lenient nullability for DTOs
model.kotlin.domain.yaml    ← Domain layer: sealed classes for enums, stricter types
```
