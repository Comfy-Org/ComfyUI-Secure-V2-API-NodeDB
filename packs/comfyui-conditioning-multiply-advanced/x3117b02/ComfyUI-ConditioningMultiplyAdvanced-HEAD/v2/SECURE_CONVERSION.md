# Conditioning Multiply Advanced — Secure Nodes V2 conversion

Upstream is pinned at `3117b024ae3756cda0b3b88e0c265256aa48e53c`.

- Python nodes: 1 registered, 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0; JavaScript-only nodes: 0; backend routes: 0.

The conversion preserves recursive conditioning scaling, all tensor scopes,
integer-token policies, metadata-key selection, six curves, three outside-window
policies, segmented timestep ranges, range intersection behavior, and input
non-mutation. It uses `CondRef.value()` and `CondRef.from_value()` under the
single `raw` capability, with explicit nesting/item/tensor bounds and no ambient
host, filesystem, network, process, route, or frontend authority.

Upstream's `pyproject.toml` references a `LICENSE` file, but commit `3117b02`
does not contain that file. The conversion does not invent licensing terms.
