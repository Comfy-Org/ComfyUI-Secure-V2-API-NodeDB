TinyTerra retains two purpose-specific refusals in the selected Core44564/overlay59bd release. Ordinary sampling remains available within its qualified scope; no entire sampler node is refused.

| Original sampler ID | Purpose refused for this release |
|---|---|
| `ttN pipeKSampler_v2` | Embedded `adv_xyPlot` caller/input rerender |
| `ttN pipeKSamplerAdvanced_v2` | Embedded `adv_xyPlot` caller/input rerender |
| `ttN pipeKSamplerSDXL_v2` | Embedded `adv_xyPlot` caller/input rerender |
| `ttN KSampler_v2` | Embedded `adv_xyPlot` caller/input rerender |
| `ttN pipeKSampler` | Cross-render Hold |
| `ttN pipeKSamplerAdvanced` | Cross-render Hold |
| `ttN pipeKSamplerSDXL` | Cross-render Hold |

Embedded XY natively reruns the sampler caller and its input closure, retaining pipe, latent, grid, individual-save and executor-cache behavior. Corrected `graph.expand_upstream_variants` requires a direct linked input, excludes the caller from the upstream traversal and permits existing literal overrides. These sampler declarations also lack expansion authority. The smallest continuation is an explicit own-pack cell/collect expansion using existing graph APIs and admitted links, followed by narrowly selected caller/input authority for native cases that remain unrepresentable. Ordered scheduling, cache behavior and native output comparisons must be qualified. Until then, use `adv_xyPlot=None` for ordinary sampling; an empty-axis fallback is also unimplemented.

Legacy Hold natively returns the prior successful live pipe and previews. This consumer creates fresh sampler state per dispatch. A feasible extension is a bounded host-owned prior-output slot keyed by tenant, workflow, node and source identity, with success-only updates, current-realm ref reissue, explicit lease/invalidation/release and failure/cancel isolation. Tests must cover Sample then Hold and the native no-prior incoming-pipe/empty-UI fallback. Pack globals and serialized live-ref tokens cannot supply this ownership contract. Select Sample in the current release.

These are current authority/lifetime constraints, not permanent SDK impossibilities. The companion JSON binds the existing native audit, all seven rows, selected consumer files, corrected SDK `f1a73e4f` and upstream planner `67e97edc`. No source, 47-ID generator, build or runtime changed.
