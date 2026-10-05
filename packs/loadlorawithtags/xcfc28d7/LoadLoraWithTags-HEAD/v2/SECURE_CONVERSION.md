# LoadLoraWithTags — Secure Nodes V2 conversion

Upstream is pinned at `cfc28d70e362695b001854172013bf643e851313`.

- Python nodes: 1 registered, 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0; JavaScript-only nodes: 0; backend routes: 0.

The conversion preserves LoRA application, bypass and zero-strength behavior,
optional prompt composition, cached trigger words, conditional and forced
CivitAI refresh, tag printing, and all original schemas. Logical LoRA catalogue
names are resolved to opaque assets; hashing and LoRA application remain on the
trusted host. CivitAI access uses the bounded integration, while its tag cache is
pack-scoped and per-user instead of the legacy process-global
`./loras_tags.json`. Arbitrary paths, filesystem access, and unrestricted
network access are removed.

The legacy cache file is not migrated because its relative path depends on the
server process working directory and has no tenant ownership. Tags are safely
repopulated through the existing CivitAI integration when requested.

Upstream's `pyproject.toml` references a `LICENSE` file, but the pinned commit
does not contain one. The conversion does not invent licensing terms.
