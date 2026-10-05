# Secure conversion record

Upstream is pinned at `ede1f33f5889f9f6d5bcb3cc54a5904869f31a41`.

## Census

- Python nodes: 4 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The census was established by importing the pinned package through ComfyUI's
normal package-registration contract and reading the four exported node IDs.

## Behavior and authority

The conversion preserves the registered pack's automatic patch orientation and
ratio selection, context-window crop and scaling metadata, image/mask padding,
color-patch generation, horizontal and vertical composition, optional second
image and mask handling, output ordering, and scalar offsets and dimensions.

These are pack-specific OpenCV, NumPy, and Torch image algorithms, retained in
the pack under permissioned raw value-mode compute. The registered paths do not
need the legacy package's unused JSON, filesystem, random, SafeTensors,
scikit-image, or Pillow imports. The secure nodes receive no filesystem,
network, subprocess, model, storage, route, frontend, or host-global authority.
The formerly unbounded output-size and pixel-buffer integers are validated
before allocation: output length is limited to 64–2048 pixels and pixel buffer
to 0–4096 pixels; malformed types, booleans, and out-of-range values fail
closed.
