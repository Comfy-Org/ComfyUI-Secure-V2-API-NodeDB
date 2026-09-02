# ComfyUI-ppm Secure Nodes V2 conversion ledger

Status: backend, frontend, and scheduler conversion complete. Retained
post/pre-CFG, conditioning selection/preprocessing, latent operations, custom
samplers, model sigma, three canonical UNet block hooks, regional attention,
and future NegPiP prompt encoding preserve the admitted source behavior.

Source tuple: `comfyui-ppm`, `https://github.com/pamparamm/ComfyUI-ppm`,
`80f6c431dd5dfd8ab01c5ae3ae52a3232ea1ee48`, `x80f6c43`.
The pristine sibling contains 46 files with mode/content digest
`9139c151de6898814f5e8d0459276d7b32c01840046faa339f1cd415d45e1c87`.

The exact source census is 33 backend node IDs, two frontend registrations
with four distinct behaviors, and six import-time scheduler registrations.
There are no model downloads or required Hugging Face weights.

## Working backend ledger

- `AttentionCouplePPM` — supported. Its canonical
  SD1/SD2/SDXL/SDXL-Refiner path now runs as one retained, paired
  `regional_attention` closure with declared CONDITIONING/MASK captures. The
  host projects those tensors once, PPM owns batch expansion and mask blending,
  and a real guest differential covers the paired pre/post calls. The distinct
  Anima/Cosmos branch is also live: the host performs its existing sampler-time
  conditioning preparation and recognized transformer wrapping while PPM owns
  the expand/merge tensor math in the same sandbox. A second real-guest
  differential covers that path. Its typed composition with `CLIPNegPip` is
  also covered: canonical models split interleaved extra conditioning into
  key/value halves, while Anima carries and region-expands its matching sign
  masks before value attention.
- `ModelAttentionSelector` — supported with registered model attention selection.
- `CLIPAttentionSelector` — supported with registered CLIP attention selection.
- `CADSPPM` — supported with a retained conditioning-preprocess closure; the
  host selects only `c_concat`/`c_crossattn` tensor leaves and owns wrapper
  reconstruction, while all CADS noise/normalization math stays pack-side.
- `CLIPTextEncodeBREAK` — supported with pack-side BREAK orchestration.
- `CLIPMicroConditioning` — supported with closed conditioning metadata.
- `CLIPTokenCounter` — supported; parsing and formatting remain pack-side.
- `ConditioningZeroOutCombine` — supported with zero/range/combine primitives.
- `CLIPTextEncodeInvertWeights` — supported; inversion remains pack-side.
- `CLIPNegPip` — supported by a capture-free future-encode closure attached
  atomically to cloned MODEL/CLIP refs. SD/SDXL token objects and textual-
  inversion vectors remain host-side; the pack receives only base encoded rows
  plus numeric weights and returns the interleaved key/value representation.
  Anima receives only its signed weight vector and returns absolute weights
  plus a bounded sign mask. The source-labelled unmaintained FLUX full-forward
  replacement and ambient Advanced CLIP monkey-patch are explicitly not
  admitted; both fail by name rather than silently changing behavior.
- `FreeU2PPM` — supported with phase-specific retained canonical-UNet block
  closures. Channel selection, slicing, sigma windowing, and Fourier filtering
  remain pack-side; full transformer options and model objects never cross.
- `Guidance Limiter` — supported with a retained pack-side post-CFG closure.
- `CFGLimiterGuider` — supported by the closed scheduled-CFG guider with
  optional sigma-window bounds; guider policy stays host-owned.
- `RescaleCFGPost` — supported with a retained pack-side post-CFG closure.
- `DynamicThresholdingSimplePost` — supported by the canonical transform.
- `DynamicThresholdingPost` — supported by the canonical transform.
- `RenormCFGPost` — supported with a retained pack-side post-CFG closure.
- `TCFGAdvanced` — supported with a retained pack-side pre-CFG closure.
- `SkipFirstStepCFG` — supported with a retained conditioning-selection
  closure; only presence booleans and scalar sigma enter the sandbox.
- `TilePreprocessorPPM` — supported with pack-side tensor math (`raw`).
- `EmptyLatentImageAR` — supported with pack-side dimension policy.
- `LatentToWidthHeight` — supported with bounded latent shape metadata.
- `LatentToMaskBB` — supported with pack-side tensor math (`raw`).
- `MaskCompositePPM` — supported with pack-side tensor math (`raw`).
- `LatentOperationTonemapLuminance` — supported as a retained latent-operation
  closure; all three tonemappers remain pack-side.
- `ConvertTimestepToSigma` — supported with scalar schedule projections.
- `EpsilonScalingPPM` — supported with a retained post-CFG closure plus the
  scalar zero-terminal-SNR schedule query; epsilon math remains pack-side.
- `CFGPPSamplerSelect` — supported: four registered host samplers and nine
  retained PPM loops. The SDE choices consume `eta`; their CPU/GPU aliases map
  to host-owned CPU/latent-device Brownian sources. The dynamic choices consume
  the gamma window, the two Euler choices consume `s_extra_steps`, and only the
  ancestral dynamic choice also consumes `eta`.
- `DynSamplerSelect` — supported with six retained PPM loops. Euler DY/SMEA
  consume `s_dy_pow` and `s_extra_steps`; ancestral DY consumes `eta` and
  `s_dy_pow`; DPM++ DY consumes `s_dy_pow`; Kohaku consumes only `eta`, so its
  source-exposed DY controls are intentionally not claimed as functional.
- `PPMSamplerSelect` — supported with two retained gamma loops. Both consume
  `cfg_pp`, `s_sigma_diff`, and the model's actual maximum sigma.
- `SamplerGradientEstimation` — supported with the closed named sampler API.
- `SamplerSEEDS2Scheduled` — supported with a retained SEEDS-2 program and two
  scalar percent-to-sigma projections. Its independent noise is tied to the
  invocation seed.
- `SamplerER_SDEScheduled` — supported with a retained ER/Reverse/ODE program
  and two scalar percent-to-sigma projections. Stochastic independent noise is
  tied to the invocation seed; ODE mode does not request noise.

Rejected: none at the node-identity level. The two source-specific exclusions
inside `CLIPNegPip` are the unmaintained FLUX replacement and an ambient
cross-pack monkey-patch; they are recorded above and fail by name.

Current backend total: 33 supported, 0 rejected, 0 pending.

## Frontend ledger

The V2 worker module uses only `/comfy/api/v2.js` definition handles. It grows
and trims paired `cond_N`/`mask_N` inputs for `AttentionCouplePPM`, and grows
and trims the trailing `mask_N` input for `MaskCompositePPM`. The dedicated
Node VM harness runs without `window`, `document`, DOM, network, storage, timer,
or parent-frame globals.

## Scheduler ledger

`ays`, `ays+`, `ays_30`, `ays_30+`, `gits`, and `beta_1_1` are supported by
the generic declarative scheduler-provider bridge. The host registers only
the six sealed names, projects a bounded scalar schedule, and runs the pack's
`ppm_scheduler_programs.provide` entrypoint in a fresh authority-free sandbox
for each calculation. The clear documented AYS intent is preserved: `ays+` is
the ten-point AYS schedule with forced sigma minimum, while `ays_30` is the
thirty-point schedule. This corrects the source's accidental middle-pair
wiring without moving either schedule algorithm into core or sharing guest
state between tenants.

## Intent-preserving corrections

The source `TilePreprocessorPPM` computes the `rescale_to_input` branch and then
returns the unscaled intermediate. V2 returns the computed branch, so the
published option now controls whether the original dimensions are restored.
Legacy `IO.COMBO` declarations are normalized to real V3 option lists so their
dropdowns do not become empty after freezing.

PPM's tensor, attention, NegPiP, FreeU, TCFG, CADS, and tonemap algorithms are
already isolated in `ppm_programs.py` and `ppm_attention_programs.py`; the AYS
and GITS schedule math is in `ppm_scheduler_programs.py`. These modules are
pack code and are not host API implementations. Every custom sampler exposed
by the three selector nodes, plus the scheduled SEEDS-2 and ER-SDE loops, is
pack-owned in `ppm_sampler_programs.py`, source-differential tested, and
exercised through a real guest process. The published retained bridge exposes
only four invocation-scoped broker verbs: bounded denoise (optionally capturing
uncond or applying one `nearest-exact` context resize), host noise
(`independent`, `ancestral`, or `brownian`), preview, and scalar schedule
parameters. Denoise is capped at three calls per interval, noise at four,
schedules at four per invocation, and previews must immediately follow an
unpreviewed denoise. Tensors preserve host-selected shape, dtype, and device
bounds. Capabilities and transferred buffers expire when the invocation
returns. None of PPM's integration algorithms moves into core.
