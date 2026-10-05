# Secure conversion record

Upstream is pinned at `1a8091c831abea905bfe060c9b501bf87fd4ad00`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 1 supported, 0 rejected, 0 pending.
- JavaScript-only nodes: 0.
- Backend routes: 1 legacy route removed; 0 V2 routes.

The actual package loader registers only `JOJR_RandomSize`. The frontend adds a
single size-list display. The legacy POST route only returned one of the eight
bundled preset tables.

## Behavior and authority

The conversion preserves the ordered preset choices and values, direct-index
selection, seeded fallback selection, marked selected size, width/height output,
hidden unique ID, and the per-node size-list display. The pinned YAML tables are
embedded in the Python and frontend modules, eliminating runtime host-file and
backend-route access. The empty upstream custom-preset directory is not treated
as authority to read arbitrary server files.

The mounted frontend has serialized display state and scoped widget listeners.
It uses safe text rendering, removes its listeners on teardown, and has no
ambient graph, canvas, DOM, storage, network, backend, or global-event access.
