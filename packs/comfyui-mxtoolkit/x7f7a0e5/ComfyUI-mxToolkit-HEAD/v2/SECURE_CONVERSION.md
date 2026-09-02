# Secure Nodes 2.0 conversion

Pinned upstream commit: `7f7a0e584f12078a1c589645d866ae96bad0cc35`.

- Backend nodes converted: 4/4.
- Rejected nodes: 0.
- Frontend modules converted: 5/5.

All four backend nodes are supported. `mxSeed`, `mxSlider`, and `mxSlider2D`
retain their value-selection behavior in the pack. `mxStop` uses the narrow
`execution.interrupt` capability to stop only the active execution while
passing its input through.

All five upstream JavaScript modules, including the frontend-only `mxReroute`
node, use `/comfy/api/v2.js` and run inside the pack iframe. They use only the
published graph, widget, queue, backend, definition, and drawing surfaces.
