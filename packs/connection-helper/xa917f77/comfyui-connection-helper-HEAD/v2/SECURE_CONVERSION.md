# Secure conversion report

- Upstream: `https://github.com/ltdrdata/comfyui-connection-helper`
- Pin: `a917f77bd02cde5aa67f427eb81e8356fffbc98e`
- Actual loader census: 0 Python nodes, 1 frontend extension, 0 routes.
- V2 census: 0 Python nodes, 1 frontend extension, 0 routes.

The conversion uses typed graph, node, input-slot, output-slot, link, widget,
and node-menu handles. Mutations are grouped into one host undo step. Widget
inputs copied from a peer are represented with the typed slot `widget` shape,
so their workflow serialization remains correct.

The only deliberate presentation change is placement: the three title-bar
canvas buttons are three entries in a host-owned node context submenu. Their
selection rules and graph mutations are preserved. No operation or authority
was dropped.

The V2 frontend has no access to `app.graph`, LiteGraph internals, ambient DOM,
backend routes, network, files, storage, or global listeners.
