# Secure Nodes V2 conversion

Upstream: <https://github.com/Fuwuffyi/ComfyUI-VisualArea-Nodes>

Pinned commit: `a139b606c61a5e71e24ad2ca382e4de361df2db8`

Release: `xa139b60`

## Census

- Backend: 2 supported, 0 rejected, 0 pending.
- Frontend: 2 supported extensions, consolidated into one typed module.
- Routes, settings, external dependencies, and model weights: none.

The pinned package's actual registration loader exports `VisualAreaPrompt` and
`VisualAreaPromptAdvanced`. Both IDs, display names, categories, static inputs,
hidden workflow inputs, outputs, and expansion behavior are preserved.

## Behavior

The frontend uses the typed node-definition, slot, property, widget, and mounted
canvas APIs. It maintains a single trailing optional conditioning socket,
renumbers connected sockets deterministically, stores each rectangle in the
owning node's serialized properties, and renders the grid on a node-local canvas.
No listener or state is shared between node instances.

The backend validates the serialized rectangles and their exact correspondence
to connected conditionings. It recreates the original bounded graph expansion
from converted `ConditioningConcat`, `ConditioningSetAreaPercentage`, and
`ConditioningCombine` nodes. The advanced node preserves both `merge_global`
branches.

## Security boundary

The guest receives opaque `CondRef` values and bounded workflow metadata. It
declares only graph-expansion authority and exact converted-node targets. It has
no filesystem, process, network, model, media, route, storage, or ambient DOM
authority. Malformed, non-finite, out-of-range, sparse, or mismatched area data
fails closed before an expansion is requested.
