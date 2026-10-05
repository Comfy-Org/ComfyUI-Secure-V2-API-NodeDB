# Secure Nodes V2 conversion

Upstream: `https://github.com/cmeka/ComfyUI-WanMoEScheduler`

Pinned commit: `a2d601ad360cd6c0fdfd7cbd118d4bfa9d40ed0a`

## Census

- Backend: 1 supported, 0 rejected, 0 pending.
- Frontend: 0 extensions and 0 JavaScript-only nodes.
- Legacy routes: 0.

The conversion preserves the registered node ID, schema, shift search, denoise
cropping, and the full/high/low sigma outputs. Model sampling stays on the
trusted host through `ModelRef.sampling_sigmas`; the pack never receives model
internals or raw tensors. The shifted sampling object is temporary and does not
patch the input model.
