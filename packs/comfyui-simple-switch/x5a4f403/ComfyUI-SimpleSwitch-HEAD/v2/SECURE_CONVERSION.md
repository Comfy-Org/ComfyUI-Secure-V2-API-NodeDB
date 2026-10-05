# Secure Nodes V2 conversion

- Upstream: <https://github.com/boobkake22/ComfyUI-SimpleSwitch>
- Pinned commit: `5a4f403a2f4aac076cee89ffe8ff4e93511c9acc`
- Census: 4 Python nodes, 0 frontend extensions, 0 routes
- Supported: 4 Python nodes; rejected: 0; pending: 0

The conversion retains the exact node IDs, display names, category, optional
socket order, wildcard/latent types, first-match behavior, audio/video subtype
rules, and diagnostic failures. Opaque values and latent refs are passed
through without replacement. The two subtype-aware switches use only the
permissioned `raw` tier to inspect latent shape and the `type`/`sample_rate`
markers required by upstream behavior. No generalized API gap was found.
