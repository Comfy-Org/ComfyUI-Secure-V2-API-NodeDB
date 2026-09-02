# Secure Nodes V2 conversion

- Pack: `tripleksampler`
- Upstream: `https://github.com/VraethrDalkr/ComfyUI-TripleKSampler`
- Pinned commit: `b35509c84ff8a82f9111418aad8611a2ec3ef216`
- Release: `xb35509c`
- Backend: 8 supported, 0 rejected, 0 pending
- Frontend: 1 supported, 0 rejected, 0 pending

## Behavior ledger

All three standard TripleKSampler nodes retain the pack's integer stage
alignment, base-step selection, manual and boundary switches, adaptive 0.01
sigma-shift refinement, stage skipping, seed offset, noise policy, overlap
warning, and dry-run calculation behavior. The two strategy selector nodes
retain their exact five- and eight-choice vocabularies. Those algorithms run in
the guest. Core supplies only the generic model transform, scalar sigma query,
latent scale, sampling, and execution-interrupt primitives.

The three optional TripleWVSampler nodes are registered as intended behavior
instead of disappearing at import time. They retain the same stage/switch
algorithms and expand three `WanVideoSampler` stages with closed kwargs,
LATENT links, seed/noise rules, and both final outputs. The external target is
permitted only through the exact
`graph.expand.external:WanVideoSampler` declaration, and only when the
installed target is a validated Secure Nodes V2 proxy. A missing or legacy
WanVideoWrapper therefore fails closed without running trusted legacy code.

WanVideo schedule construction and adaptive refinement remain pack-side. The
exact scheduler tree from `kijai/ComfyUI-WanVideoWrapper` commit
`aa9f4749587c0f8a5041a56bcc4e4a07ca76c4f0` is vendored under Apache-2.0;
only its parent-pack logger import was replaced with a standard-library logger.
The upstream `multitalk` inline schedule is reproduced in the wrapper because
that revision advertises it without implementing it in `get_scheduler()`.
Dependencies are fixed in `pyproject.toml` for the managed pack runtime; node
execution never installs or downloads Python packages.

Only the CausVid boundary schedule needs model metadata. It uses the bounded,
vendor-scoped `integrations.wanvideo.transformer_dim` projection. No model,
weights, scheduler object, sampler implementation, or node algorithm crosses
that API seam.

## Frontend and notifications

The dynamic visibility and dry-run button are implemented with the V2
definition/widget/source/graph/command APIs from `/comfy/api/v2.js`. Execution
returns closed `triple_ksampler_overlap` and `triple_ksampler_dry_run` UI
payloads, and the executed hook projects them into bounded notifications. The
extension has no ambient DOM, parent realm, same-origin access, timers,
unrestricted network, legacy app object, or host-prototype mutation.

## Security result

The pack requests no raw tensors, filesystem, subprocess, network, secrets,
credentials, output, model-download, or runtime-install capability. Sampling,
interrupt, graph expansion, exact converted dependency composition, and the
single WanVideo scalar projection are independently permission-gated. No node
is rejected and no intended behavior or API gap remains.
