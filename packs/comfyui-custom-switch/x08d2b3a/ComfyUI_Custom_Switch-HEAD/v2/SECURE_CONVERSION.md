# ComfyUI Custom Switch — Secure Nodes V2

Upstream is pinned at `08d2b3a08e65e3bb8f334e65a073f852a817bd57`.

## Census

- Python nodes: 5 supported, 0 rejected, 0 pending.
- Frontend extensions: 4 supported, 0 rejected, 0 pending.
- Backend routes and JS-only graph nodes: 0.

## Conversion

The four no-op orchestration nodes retain their exact IDs, names, category,
output-node status, and empty execution result. `AutomaticImageSwitcher`
retains its three optional inputs, first-connected priority, reference identity,
and 64×64 RGB zero-image fallback. Only that fallback needs the `raw`
capability.

The four ambient LiteGraph prototype extensions are consolidated into one
typed module. It uses document-scoped node queries, `GroupHandle.nodes()`,
`NodeHandle.setMode()`, one graph batch per edit, mounted controls, and bounded
workflow properties. Both `[[group:tag]]` controllers preserve exclusive and
multi-select behavior; both group controllers preserve radio selection. Bypass
controllers use `bypass`, while muters use `never`.

The legacy `localStorage` title backup and duplicate-ID node recreation are
removed. Secure graph handles are graph-scoped, so duplicate numeric node IDs
across subgraphs cannot alias; titles and controller properties are already
part of the workflow. One shared observer set and bounded refresh timer replace
the four prototype hooks and per-node polling loops, and are released when the
last controller disappears.

No frontend permission, private route, filesystem, storage, network, or shared
API change is required.
