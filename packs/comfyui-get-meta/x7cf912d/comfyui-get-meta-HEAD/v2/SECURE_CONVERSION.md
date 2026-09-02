# Secure Nodes V2 conversion

Pinned upstream commit: `7cf912d2804d037c9f2a6a679a8b16a6e6d9f845`.

- Backend nodes supported: 8/8.
- Backend nodes rejected: 0.
- Backend nodes pending: 0.
- Frontend extensions supported: 1/1 (`shinich39.GetMeta`).
- Frontend extensions rejected: 0.
- Frontend extensions pending: 0.

Every node reads metadata only from the managed input asset selected by the
image loader directly connected to its `image` input. The guest receives an
opaque asset ref and bounded bytes; it never receives a filesystem path. PNG,
JPEG, WebP, BMP, GIF, and TIFF inputs are size- and pixel-bounded before their
metadata is interpreted.

The frontend imports only `/comfy/api/v2.js`. It normalizes a unique node
definition title to its backend type ID while a prompt is being built and
restores the visible query immediately afterward. Executed values are copied
back into the node's derived widget through the V2 widget facade. It does not
fetch image bytes, access a parent window or DOM, or register a backend route.

`ABS_PATH` is the sole deliberate behavior change. That query now fails closed
because disclosing a host filesystem path is incompatible with the Secure
Nodes boundary. `PATH` and `REL_PATH` return the selected asset's logical name,
and `DIR_NAME` returns only its logical managed-input subfolder. This is not a
node rejection; all eight node IDs remain supported.
