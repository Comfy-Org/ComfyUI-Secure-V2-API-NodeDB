# Secure Nodes V2 conversion

- Upstream: <https://github.com/nosiu/comfyui-text-randomizer>
- Pinned commit: `9808d4315d0c88ecb448bc6c1ad1774470dfb172`
- Release key: `x9808d43`

## Census

- Five registered Python nodes: `RandomizeText`, `RandomizeTextWithCheck`,
  `RandomTextChoice`, `ConcatText`, and `ShowText`.
- One frontend extension: `ComfyUI.text-randomizer-01`.
- No backend routes and no JavaScript-only nodes.

All five nodes and the frontend extension are supported. The backend uses no
permissions or host capabilities. Seeded selection preserves Python's upstream
Mersenne-Twister sequence while using a per-execution generator so one node
cannot mutate another node's random state.

The frontend uses typed node and widget lifecycle hooks. Live delimiter
validation, the read-only result fields, execution updates, and connection
reset behavior remain per node. It does not access ambient DOM, host globals,
storage, backend routes, or the network.
