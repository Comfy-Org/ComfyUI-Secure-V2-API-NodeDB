# Secure conversion record

Upstream is pinned at `5dd91d71bff801e5cb1daa56ca5f85d08490e089`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The two bundled screenshots and README are inert documentation assets. They do
not add registrations or runtime authority.

## Behavior and authority

`ZImageLatent` preserves all 33 ordered resolution choices, batch bounds,
dimension-string parsing, multiple-of-16 alignment, output order and names,
category, and the intended display name declared by the pinned node module.
Every valid selection produces the same all-zero, four-channel latent shape and
the same width and height as the source.

The source package's root module omits its own display-name mapping from its
exports. V2 exposes the `Z Image Latent` name that the pinned node module itself
declares, rather than retaining that packaging oversight.

The legacy implementation selected a host device and allocated a raw tensor.
V2 instead requests a bounded empty latent through `sdk.LatentRef.empty`, which
preserves the value and layout without exposing a device or tensor. The node
declares refs but no permissions and has no filesystem, network, subprocess,
storage, frontend, route, model, or host-global authority. Direct malformed
strings retain their parsing failures. Parseable direct values outside the
SDK's documented allocation bounds fail closed before allocation.
