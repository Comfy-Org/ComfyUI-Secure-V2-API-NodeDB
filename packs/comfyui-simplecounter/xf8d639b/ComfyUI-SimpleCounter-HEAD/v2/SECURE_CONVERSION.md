# Secure Nodes V2 conversion

- Upstream: <https://github.com/AonekoSS/ComfyUI-SimpleCounter>
- Pinned commit: `f8d639b2849b0956309eb662b41a264f1dca5d46`
- Release key: `xf8d639b`

## Census

- One registered Python node: `Simple Counter`.
- One frontend extension: `SimpleCounter`.
- No backend routes and no JavaScript-only nodes.

The node and extension are supported. The Python node is an authority-free
integer passthrough and remains non-idempotent. The frontend keeps one counter
per node instance, supplies sequential values only while prompts are being
serialized, and resets from the current `start` value after an accepted queue
submission. Rejected submissions and interruptions do not add a second reset.

The conversion uses typed widget serialization and queue lifecycle hooks only.
It has no ambient DOM, backend, storage, filesystem, network, model, tensor, or
subprocess authority.
