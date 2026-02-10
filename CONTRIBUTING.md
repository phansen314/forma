# Contributing to Forma

Forma is a spec-and-examples repo. The most impactful contribution is a **new target profile** — a satellite document and reference doc that teaches agents how to generate code for a language or persistence layer.

## Adding a Target Profile

A complete target profile contribution includes three files:

### 1. Example profile: `examples/birdtracker.{target}.yaml`

A satellite document for the existing BirdTracker model showing your target's configuration.

**Required sections:**
- `target:` — target identifier (e.g., `kotlin`, `sql`, `typescript`)
- `globals:` — target-wide settings (package/module, conventions)
- `type_mappings:` — how Forma primitives map to target types

**Common optional sections:**
- `types:` — representation strategy + per-type overrides (style, annotations, interfaces)
- `enums:` — enum representation strategy + per-enum overrides
- `unions:` — union representation strategy
- `relationships:` — FK naming, join strategies
- `indexes:` — target-specific indexing (SQL profiles)
- `interfaces:` — generated interfaces (typed language profiles)
- `derived_types:` — DTOs derived from types (layer profiles)

Use the existing examples as templates:
- [`examples/birdtracker.kotlin.yaml`](examples/birdtracker.kotlin.yaml) — typed language profile
- [`examples/birdtracker.sql.yaml`](examples/birdtracker.sql.yaml) — database DDL profile

### 2. Reference doc: `skill/references/{target}-profile.md`

Documentation that agents read when generating code for your target.

**Required structure** (follow the existing pattern exactly):
1. **Overview** — one paragraph explaining what the profile controls
2. **Format** — fully annotated YAML showing every section with inline comments explaining each option
3. **Generated Output Example** — complete output the agent would produce from the BirdTracker model
4. **Design Notes** — rationale for key decisions (why this enum strategy, why this union representation, etc.)

Use the existing references as templates:
- [`skill/references/kotlin-profile.md`](skill/references/kotlin-profile.md)
- [`skill/references/sql-profile.md`](skill/references/sql-profile.md)

### 3. Update `CLAUDE.md` and `README.md`

Add your new files to the repo structure blocks in both files.

## Style Guidelines

### YAML files
- Header comment block: model name, "Target Profile" or "Validation Satellite", satellite reference
- Match the comment style of existing examples (see `birdtracker.kotlin.yaml`)
- Use inline comments to explain non-obvious choices
- All type/field names must match `birdtracker.forma` exactly

### Reference docs
- Markdown with fenced code blocks
- Annotated YAML in the Format section (comments explain every option)
- Generated output should be complete and realistic — not stubs
- Design Notes should explain the *why*, not repeat the *what*

### Naming
- File names: `birdtracker.{target}.yaml`, `{target}-profile.md`
- Target identifiers: lowercase, no spaces (e.g., `kotlin`, `sql`, `typescript`, `graphql`)
- Use the same target identifier in the filename and the `target:` field

## Submission Process

1. Fork the repo
2. Create a branch: `profile/{target}` (e.g., `profile/typescript`)
3. Add your three files
4. Verify all type/field references match `birdtracker.forma`
5. Open a pull request with a brief description of key design decisions

## Other Contributions

- **Spec clarifications**: Open an issue describing the ambiguity before submitting a PR
- **New examples**: Additional model files beyond BirdTracker are welcome in `examples/`
- **Validation satellites**: Follow the pattern in `examples/birdtracker.validate.yaml`
- **Skill improvements**: Changes to `skill/SKILL.md` or reference docs — open an issue first to discuss

## Questions?

Open an issue. For design discussions about where something belongs (hub vs. satellite, structure vs. validation), reference the decision boundary in `CLAUDE.md` under "Key Decision Boundaries."
