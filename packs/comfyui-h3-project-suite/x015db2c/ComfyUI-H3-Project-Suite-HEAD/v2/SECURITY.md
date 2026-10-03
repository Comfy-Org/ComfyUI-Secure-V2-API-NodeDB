# Secure Nodes V2 security model

This conversion is confined by the Secure Nodes V2 runtime.

- Python imports only `torch`, the standard library, and the public
  `comfy_api.latest` surface.
- It does not import ComfyUI internals, register server routes, open arbitrary
  paths, start programs, or patch host model/layout functions.
- Video/audio latent buffers are copied across the device channel. Live VAE
  and conditioning objects stay host-owned behind typed references.
- Saved latents and videos use the managed output broker. Loads resolve a
  logical output asset before reading a state dictionary.
- Project manifests live in tenant-scoped pack storage and accept only bounded
  plain project names. Route requests are bounded and mounted by the host under
  the pack's private route base.
- The frontend imports only `/comfy/api/v2.js`. It receives its DOM through a
  mounted sidebar container and uses neither ambient `window`/`document` nor
  localStorage, IndexedDB, raw fetch, or global keyboard listeners.

The manifest grants each node and route only the domains it uses. The tests
exercise both the Python guest boundary and the frontend-source boundary.
