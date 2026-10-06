# Image Tiled Nodes — Secure Nodes V2

Split an IMAGE batch into overlapping tiles and feathered masks, then merge the
processed tiles using the bounded TILE_INFO data socket. The original Torch
algorithms run pack-side in the raw-compute guest; no host services are required.

Compatibility and resource limits are recorded in `SECURE_CONVERSION.md`.
