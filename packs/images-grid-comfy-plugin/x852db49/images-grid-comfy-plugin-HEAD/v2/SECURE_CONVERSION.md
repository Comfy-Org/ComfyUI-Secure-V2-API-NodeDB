# Images Grid Secure Nodes V2 conversion

Pinned upstream: `https://github.com/LEv145/images-grid-comfy-plugin` at
`852db490ef93702e1c68fe9774bdf65aaa7d3574`.

## Census and disposition

- Backend nodes: 5 supported, 0 rejected, 0 pending.
- Frontend registrations: 0.
- Server routes and other runtime registrations: 0.

All image, latent, Pillow, and annotation behavior remains pack-side under the
permissioned `raw` tier. `GridAnnotation` returns a bounded plain-data
descriptor instead of trying to carry a live Pillow font object across the
sandbox boundary; the consuming grid node reconstructs the same vendored
Roboto font inside the guest. The vendored font bytes are unchanged.

The conversion adds only resource bounds: 4,096 input images, 16,384 pixels on
an output axis, and 512 MiB for a produced batch. It adds no filesystem,
network, model, or host-object authority.
