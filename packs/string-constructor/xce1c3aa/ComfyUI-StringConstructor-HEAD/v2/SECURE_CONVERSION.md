# Secure conversion record

Upstream is pinned at `ce1c3aab3dd198dcb279c45573428cf41d271843`.

## Census

- Python nodes: 4 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The actual V3 entrypoint returns the current String Formatter and Validate Dict
nodes plus their two deprecated IDs. The registry's historical one-node count is
not the package's current runtime census.

## Behavior and authority

The conversion retains the pack's current ComfyUI schema implementation,
formatter, validation rules, PreviewText status, recursive mode, safe mode,
unsafe mode, custom `DICT` socket, and deprecated node identities. It removes
the redundant external `frozendict` dependency because all supported immutable
dictionary implementations already satisfy Python's `Mapping` contract.

All four nodes execute with no host capabilities. Pack-side limits bound input
dictionary key count/key length, template size, recursive passes, and formatted
output size. The pack has no file, network, model, storage, graph, backend,
frontend, subprocess, or tensor authority.
