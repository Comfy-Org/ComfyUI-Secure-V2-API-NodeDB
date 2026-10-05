# Secure conversion record

- Upstream: `https://github.com/deepme987/ComfyUI-workflow-prettier`
- Pin: `dbfef86c7c5f2f38c3b49e55acdbc02e7859433b`
- Census: 1 Python node, 1 frontend extension, 0 backend routes
- Supported: 1/1 Python nodes and 1/1 frontend extensions
- Frontend permissions: none
- Python permissions: none

The conversion keeps every layout and selection operation but replaces direct
access to `app.graph`, `_nodes`, `_groups`, `links`, node fields, and
`LGraphCanvas.prototype` with `GraphHandle`, `NodeHandle`, `GroupHandle`, node
definition contributions, commands, and the action bar.

Local undo state is keyed by editing-session id and visible graph id, capped at
10 snapshots, cleared when the document closes, and resolves handles again at
restore time so removed nodes or groups cannot receive stale writes. All graph
mutations are confined to the currently visible graph and use `graph.batch()`.

The previous empty-canvas submenu is intentionally surfaced as host commands
and a Prettify action-bar button because Secure Nodes does not patch renderer
prototype menus. This is a placement change, not a behavior gap: all four quick
layouts, equalize, undo, and add-node actions remain available. Node-selection
alignment remains in the node context menu.
