# Secure Nodes V2 conversion

Upstream: `https://github.com/Ugleh/ComfyUI-interactive-crop`

Pinned commit: `7c6e815fdc66989573e4152a651c8d42d4ed384b`

The one Python node and one frontend extension are supported. The legacy
process-global HTTP callback and custom websocket event are replaced by the
host's invocation-scoped, one-use interaction broker. Preview files remain
host-managed identities. The crop algorithm remains pack-side under the
explicit raw tensor tier.

The mounted canvas owns pointer gestures locally, so the user no longer needs
to select the node before drawing. This removes the legacy graph-canvas event
hook without changing the crop operation. The four-minute timeout matches the
pinned implementation (the older six-hour README statement was stale).

The bundled upstream `node.zip` is retained in the pristine snapshot only; it
is not used at runtime and is not duplicated in the V2 tree.
