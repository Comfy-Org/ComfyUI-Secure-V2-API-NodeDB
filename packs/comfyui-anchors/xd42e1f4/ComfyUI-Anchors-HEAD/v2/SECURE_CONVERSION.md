# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/DrJKL/ComfyUI-Anchors`
- Full commit: `d42e1f474b243a2dfb1ae860ca314d44fdd2608c`
- Git tree: `614a3ae94adab2cfd4121e952e011c872b0cdbc7`
- Release key: `xd42e1f4`
- Commit date: `2024-06-14T06:43:57Z`

The pristine sibling is an exact materialization of all 20 tracked files at
that commit. The compatibility source remained read-only during conversion.

## Census and retained behavior

Upstream registers no backend nodes and one frontend extension,
`drjkl.custom_nodes.anchors`. That extension owns exactly one frontend-only
virtual type, `⚓ Anchor`, in category `utils`. Each anchor serializes the
`waypoint`, `waypoint_x`, and `waypoint_y` widgets. Moving it refreshes the two
coordinate widgets; the bare `a` and `d` keys move cyclically to the previous
or next anchor, centre it, and select it. A single anchor recentres itself.

V2 declares that node through `comfy.defs.define`, commits positions from
`comfy.onNodeMoved`, and registers the two shortcuts with canvas scope so they
do not fire while the user types. `graph.nodesOfType`, `graph.selection`,
`graph.centerOn`, and `graph.select` retain the navigation lifecycle without
global DOM listeners or renderer classes.

## Authority and API result

The pack has no backend execution, permissions, routes, network, filesystem,
subprocess, model, worker, storage, or secret authority. Its frontend uses only
the published graph, definition, movement, workflow, palette, and command
facades. It imports only `/comfy/api/v2.js` and runs in the opaque Secure Nodes
frontend sandbox.

No shared/core API change and no pack algorithm in core were needed. The old
class changed its title to only the anchor glyph while collapsed and used a
renderer colour getter to tint the most recently clicked anchor immediately.
Those renderer-owned presentation details are intentionally not recreated.
The frozen V2 renderer still collapses the node and retains the upstream
black/yellow default palette while preserving all saved state and workflow
navigation behavior. The legacy purple group highlight is likewise cosmetic
renderer styling and is not persisted into the workflow.

## Frozen API pair

This release is sealed against:

- Python stub SHA-256:
  `e3d18332e216894bbd5f2116a3adb184efac273f235d91da6a20dff924d610f1`
- TypeScript stub SHA-256:
  `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`
