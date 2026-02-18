# SQL Target Profile Spec

## Overview

A satellite document that provides SQL-specific generation directives. The agent reads this alongside the core structural spec (`model.forma`) when generating DDL for a relational database.

This file does **not** redefine structure. It tells the generator **how** to express that structure as database schema — table layout, column types, constraints, indexes, and relationships.

---

## Format

```yaml
target: sql

# ──────────────────────────────────────
# Type mappings — atoms to SQL column types
# ──────────────────────────────────────
type_mappings:
  UUID: UUID
  string: VARCHAR(255)
  text: TEXT
  int: INTEGER
  float: DOUBLE PRECISION
  bool: BOOLEAN
  datetime: TIMESTAMPTZ
  date: DATE
  json: JSONB

# ──────────────────────────────────────
# Emitters — named output contexts
# ──────────────────────────────────────
# `atoms:` is a reserved key — shared base type resolution for domain atoms.
# Named emitters (schema:, etc.) contain per-emitter settings.
emitters:
  atoms:
    BirdId: UUID              # domain atom → base type (resolved via type_mappings)
    UserId: UUID
    Email: string

  schema:
    # Generation settings
    dialect: postgresql
    # postgresql → PostgreSQL-specific syntax (TIMESTAMPTZ, JSONB, gen_random_uuid(), etc.)
    # mysql      → MySQL-specific syntax (DATETIME, JSON, UUID(), etc.)
    # sqlite     → SQLite-specific syntax (TEXT for most types, no native UUID)

    schema: public
    # Target schema name. Tables are created in this schema.

    naming:
      tables: snake_case_plural          # User → users, Bird → birds
      columns: snake_case                # createdAt → created_at, wingspanCm → wingspan_cm
      foreign_keys: "{table}_{column}"   # e.g., observations.bird_id
      join_tables: "{table1}_{table2}"   # e.g., birds_tags (alphabetical by default)
      indexes: "idx_{table}_{columns}"   # e.g., idx_users_username
      primary_keys: "pk_{table}"         # e.g., pk_users (constraint name)
      unique_constraints: "uq_{table}_{column}"
      # Templates use {table}, {column}, {columns}, {table1}, {table2} placeholders.
      # {table} is the snake_case_plural table name.
      # {columns} joins column names with underscores.

    primary_key:
      strategy: table
      # table → one PK per table (usually `id`), inferred from shapes with an `id` field
      # none  → no auto-PK generation, define explicitly per shape

      generate_pk_default: true           # DEFAULT gen_random_uuid() on PK columns
      timestamps:
        created_at_default: NOW()         # DEFAULT NOW() on created_at columns
        updated_at_trigger: true          # auto-update via BEFORE UPDATE trigger

    shape: embedded_columns
    # embedded_columns → value shapes flattened with prefix: location_latitude, location_longitude
    # json_column      → value shapes stored as JSONB in a single column
    # separate_table   → value shapes normalized into their own table with FK

    choice: native_enum
    # For all-bare choices (enum-like):
    #   native_enum      → CREATE TYPE ... AS ENUM (...) — native database enum
    #   check            → VARCHAR + CHECK constraint
    # For fielded choices (union-like):
    #   jsonb_column     → single JSONB column with discriminator (default for fielded)
    #   single_table     → type column + nullable variant columns
    #   separate_tables  → one table per variant with shared PK

    # Per-name overrides — generator infers concept type from hub
    Habitat: check
    # Habitat uses CHECK because it appears in a [Habitat] collection field,
    # which maps to a text array — native enums can't be array elements
    # in all PostgreSQL versions without explicit casts.

# ──────────────────────────────────────
# Relationships — FK and join table conventions
# ──────────────────────────────────────
relationships:
  one_to_many:
    fk_column: "{target}_id"            # observations.bird_id
    fk_constraint: true                  # generate REFERENCES constraint
    on_delete: CASCADE                   # CASCADE, RESTRICT, SET NULL, NO ACTION

  many_to_one:
    fk_column: "{target}_id"
    fk_constraint: true
    on_delete: RESTRICT

  many_to_many:
    join_table: "{source}_{target}"     # birds_tags
    source_fk: "{source}_id"
    target_fk: "{target}_id"
    on_delete: CASCADE

# ──────────────────────────────────────
# Indexes — per-shape index definitions
# ──────────────────────────────────────
indexes:
  User:
    - columns: [username]
      unique: true
    - columns: [email]
      unique: true

  Bird:
    - columns: [name_common]            # embedded column name (ScientificName.common)
    - columns: [status]

  Observation:
    - columns: [timestamp]
    - columns: [bird_id]                # FK column — speeds up joins
    - columns: [observer_id]
    - columns: [location_latitude, location_longitude]
      name: idx_observations_location   # explicit name overrides template

  Tag:
    - columns: [label]
      unique: true
```

---

## Generated Output Example

Given the hub (`birdtracker.forma`) and this SQL profile, the agent generates:

```sql
-- Generated from birdtracker.forma + birdtracker.sql.yaml
-- Target: PostgreSQL (public schema)

-- ──────────────────────────────────────
-- Enum types (all-bare choices → native_enum)
-- ──────────────────────────────────────

CREATE TYPE conservation_status AS ENUM (
    'least_concern', 'vulnerable', 'endangered', 'critical', 'extinct'
);
-- Habitat uses CHECK strategy (see birds table) — no CREATE TYPE here.

-- ──────────────────────────────────────
-- Trigger function for updated_at auto-update
-- ──────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ──────────────────────────────────────
-- Tables
-- ──────────────────────────────────────

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(255) NOT NULL,
    email       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),       -- from Timestamped mixin
    updated_at  TIMESTAMPTZ,                              -- from Timestamped mixin
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE birds (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_common      VARCHAR(255) NOT NULL,                -- ScientificName (embedded_columns)
    name_scientific  VARCHAR(255) NOT NULL,                -- ScientificName (embedded_columns)
    status           conservation_status NOT NULL,
    habitats         TEXT[] NOT NULL DEFAULT '{}',          -- [Habitat] → text array + CHECK
    description      TEXT,
    wingspan_cm      DOUBLE PRECISION,
    photo_url        VARCHAR(255),
    metadata         JSONB,                                -- {string, json}? → JSONB
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),   -- from Timestamped mixin
    updated_at       TIMESTAMPTZ,                          -- from Timestamped mixin
    CONSTRAINT chk_birds_habitats CHECK (
        habitats <@ ARRAY['forest','wetland','grassland','coastal','urban']::TEXT[]
    )
);

CREATE INDEX idx_birds_name_common ON birds (name_common);
CREATE INDEX idx_birds_status ON birds (status);

CREATE TRIGGER trg_birds_updated_at
    BEFORE UPDATE ON birds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp           TIMESTAMPTZ NOT NULL,
    location_latitude   DOUBLE PRECISION,                  -- Location? (embedded_columns, nullable)
    location_longitude  DOUBLE PRECISION,                  -- Location? (embedded_columns, nullable)
    location_altitude   DOUBLE PRECISION,                  -- Location? (embedded_columns, nullable)
    notes               TEXT,
    count               INTEGER NOT NULL,
    media               JSONB,                             -- MediaAttachment? (fielded choice → JSONB)
    bird_id             UUID NOT NULL REFERENCES birds(id) ON DELETE CASCADE,
    observer_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

CREATE INDEX idx_observations_timestamp ON observations (timestamp);
CREATE INDEX idx_observations_bird_id ON observations (bird_id);
CREATE INDEX idx_observations_observer_id ON observations (observer_id);
CREATE INDEX idx_observations_location ON observations (location_latitude, location_longitude);

CREATE TRIGGER trg_observations_updated_at
    BEFORE UPDATE ON observations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE tags (
    id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label  VARCHAR(255) NOT NULL,
    CONSTRAINT uq_tags_label UNIQUE (label)
);

-- ──────────────────────────────────────
-- Join tables (N:M relationships)
-- ──────────────────────────────────────

CREATE TABLE birds_tags (
    bird_id  UUID NOT NULL REFERENCES birds(id) ON DELETE CASCADE,
    tag_id   UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (bird_id, tag_id)
);
```

---

## Design Notes

**Atom transparency in SQL**: Domain atoms like `BirdId` and `Email` resolve to their base types (`UUID`, `string`) which then map to column types (`UUID`, `VARCHAR(255)`) through `type_mappings`. There is no wrapping — SQL has no equivalent of value classes or branded types. The atom name disappears entirely in the generated DDL; its only role is providing semantic clarity in the hub.

**Value shape embedding**: The default `shape: embedded_columns` strategy flattens value shapes into prefixed columns on the parent table: `ScientificName` on Bird becomes `name_common` and `name_scientific`. The prefix is the field name from the parent shape. When the parent field is nullable (`location: Location?`), all embedded columns become nullable regardless of their nullability in the value shape — the whole group is either present or absent. The `json_column` alternative stores the value shape as a single JSONB column, which avoids column proliferation but loses type-level constraints.

**Choice strategies**: All-bare choices (like `ConservationStatus`) map to `CREATE TYPE ... AS ENUM` by default. The `check` override is needed when the choice appears as an array element (`habitats: [Habitat]`) because PostgreSQL text arrays with CHECK constraints are more portable than enum arrays. Fielded choices (like `MediaAttachment`) default to `jsonb_column` — a single JSONB column with a `type` discriminator field — since they represent polymorphic values that don't warrant their own tables.

**Naming convention templates**: The `naming:` section uses `{table}`, `{column}`, `{columns}`, `{table1}`, and `{table2}` placeholders. `{table}` is always the snake_case_plural table name (not the PascalCase shape name). For join tables, `{table1}` and `{table2}` are sorted alphabetically. Explicit `name:` on an index overrides the template.

**Relationship inference from cross-references**: The generator infers cardinality by cross-referencing field types between shapes: `observations: [Observation]` on Bird paired with `bird: Bird` on Observation yields 1:N with a `bird_id` FK on the observations table. `tags: [Tag]` on Bird paired with `birds: [Bird]` on Tag yields N:M with a `birds_tags` join table. The `relationships:` section controls FK constraints, ON DELETE behavior, and naming — not the cardinality itself.

**Timestamp handling**: When the hub uses a `Timestamped` mixin, the SQL profile controls how those fields behave at the database level. `created_at_default: NOW()` adds a DEFAULT clause so inserts don't need to supply a timestamp. `updated_at_trigger: true` generates a shared trigger function (`update_updated_at`) and per-table triggers that automatically set `updated_at` on every UPDATE. The trigger approach is more reliable than application-level updates.
