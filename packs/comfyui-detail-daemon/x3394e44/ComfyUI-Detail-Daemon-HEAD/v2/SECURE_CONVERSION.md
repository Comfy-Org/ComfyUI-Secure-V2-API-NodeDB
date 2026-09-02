# Secure Nodes V2 conversion

Pinned upstream: `https://github.com/Jonseed/ComfyUI-Detail-Daemon` at
`3394e44afea04ed0188fb37b21f0d9952469766b`.

## Census

- Backend: 5 supported, 0 rejected, 0 pending.
- Frontend: 1 extension supported, 0 rejected, 0 pending.

The two stateless sigma nodes keep their schedule and plotting algorithms in
this pack. `DetailDaemonSamplerNode`, `DetailDaemonSamplerGUINode`, and
`LyingSigmaSampler` keep their sigma-adjustment formulas here too. They retain
a prompt-scoped `model_sigma` node closure and wrap an opaque sampler; the host
continues to own the selected sampler, model call, model weights, and sampling
state. The closure receives only the current sigma, the bounded schedule, CFG,
and (for Lying Sigma) host-projected percent bounds, then returns a same-shaped
sigma tensor.

The graph editor uses the V2 canvas widget. Drawing, hit testing, drag behavior,
tooltips, reset, and widget updates remain pack code inside the isolated
frontend realm. It has no parent DOM, same-origin, or unrestricted network
access.

## Authority

- `closures`: the three sampler wrappers only.
- `raw`: creation of a new sigma schedule and the temporary plot image.
- `ui`: host-owned temporary preview for the graph node.

There is no filesystem path, network, subprocess, runtime install, host import,
model download, or model-weight access. The pristine `requirements.txt` and
`node.zip` remain in the preserved upstream snapshot but are not shipped in the
V2 tree; `matplotlib` is the pack's sole declared runtime dependency.

## Evidence

The focused conversion suite checks the exact pristine and V2 censuses,
schedule/interpolation differentials, all five nodes in one real guest process,
the three wrapped samplers against pristine behavior, capability denials, the
isolated canvas frontend, manifest/stub freshness, cache/symlink hygiene, and a
byte-exact patch-pair round trip. Full GPU diffusion inference is not a pack
behavior and is not repeated here; representative host sampler/model refs run
through the real guest transport.
