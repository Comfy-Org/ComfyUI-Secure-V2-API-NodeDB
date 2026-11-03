# Secure Nodes V2 conversion

Pinned upstream commit: `057a913ed3c04cbfb756e1a3dbfc398a6bd4044f`
Upstream: `https://github.com/ClownsharkBatwing/RES4LYF`

## Census and terminal status

- The pinned package has 300 backend node ids. One of them,
  `ConditioningMultiply`, is an id ComfyUI core registers itself
  (`nodes.py:163` and `:2109` on core 6257422b, "Conditioning (Multiply)").
  Core's loader skips any custom node id that core already has, for the class
  and the display name alike (`nodes.py:2314-2322`). So with the original
  installed, core's node serves that id and the original's never registers.
  This pack leaves the id out as well, and core's node keeps serving it
  (`tests/test_core_ids.py` checks this against core's full id set).
- Every other id (299) is registered with its original schema, frozen from the
  original (`_frozen_nodes.json`). The served node info equals the original's
  (`tests/test_res4lyf_schemas.py`).
- Converted (25 of the 299):
  - `ClownsharKSampler_Beta`, within the reduced envelope below, including the OPTIONS it can apply exactly;
  - the options nodes `SharkOptions_Beta`, `ClownOptions_DetailBoost_Beta` and `ClownOptions_SigmaScaling_Beta`;
  - the value nodes `TextBox1`, `TextBox2`, `TextConcatenate`, `SetImageSize`, `SetImageSizeWithScale` and
    `SeedGenerator`;
  - the sigma nodes `Sigmas Power`, `Sigmas Mult`, `Sigmas From Text`, `Sigmas Split Value`, `Sigmas Rescale`,
    `Sigmas Easing` and `Sigmas Resample`;
  - the image nodes `Film Grain`, `Image Grain Add`, `Frames Slice`, `Frame Select`, `Image Repeat Tile To Size`
    and `VAEEncodeAdvanced`;
  - the latent nodes `LatentUpscaleWithVAE` and `EmptyLatentImageCustom`.
- Every other id is refused by name at queue time ("not converted to Secure
  Nodes V2 yet"), and again at run time. Nothing is approximated. Five
  name their own reason:
  - `Image Sharpen FS` blurs with OpenCV, which the guest does not have, and
    runs its blend on CUDA unconditionally (`images.py:472-475`). So the
    original fails on any host without CUDA.
  - `ReSDPatcher` patches the model by swapping the classes of the diffusion
    model's own modules for RES4LYF's (`models.py:622-647`). No SDK model
    transform does that. Its style code also moves tensors to CUDA
    unconditionally (`style_transfer.py:428`), so the original fails on any
    host without CUDA.
  - `SigmasPreview` draws its plot with matplotlib
    (`helper_sigma_preview_image_preproc.py:126-139`), which the guest does
    not have. A drawing without matplotlib would not be byte-exact.
  - `Image Gaussian Blur` blurs with OpenCV (`images.py:844`), which the
    guest does not have.
  - `Latent to Cuda` moves the latent's tensors to the device it names, CUDA
    or the CPU (`nodes_latents.py:707-750`). Where a V2 latent lives is the
    host's choice, and on a host without CUDA the original fails.
- Requires guest SDK base 0cd9adec or later (`ImageRef.from_value`, and SIGMAS
  read and written as tensors).
- Scheduler names: like the original, the pack adds `beta57` and
  `bong_tangent` to Core's scheduler list. It does this through manifest
  scheduler providers (`schedulers.py`), so any sampler node can use them.
- Frontend extensions: not served (not converted).

## ClownsharKSampler_Beta: what runs where

- RES4LYF's own Runge-Kutta loop runs in the guest as a custom-sampler closure.
  These are the upstream files in `res4lyf_core/`, copied unchanged except for
  their import lines. `res4lyf_core/VENDOR.json` lists every rewritten line,
  with source and destination hashes.
- Model evaluation stays on the host behind the closure broker. The node never
  sees the model, the conditioning objects or the weights. The broker allows
  3 model evaluations per step.
- The node retains one sampler program per prompt and reuses it for every pass
  and run. Programs live until their prompt ends, so they never accumulate.
- Schedules:
  - Core's schedulers come from one zero-evaluation host pass.
  - `beta57` and `bong_tangent` are computed in the guest by the same provider
    functions, on the model's sigma table read exactly from one
    zero-evaluation pass. They fall back to the registered providers when that
    table cannot be confirmed.
  - Connected SIGMAS are read as given.
- The node reproduces the original's arithmetic exactly:
  - the float64 outer schedule;
  - RES4LYF's init noise;
  - Core's noise scaling on that schedule;
  - the loop;
  - the post-sample mask blend;
  - both output latents and the OPTIONS output.
  Outputs are bitwise equal to the original's (`tests/v2_parity.py`).
- Apart from the main sampling pass, the node makes only zero-evaluation host
  passes: the schedule, and the denoised output.
- Both output latents carry the loop's final denoised estimate, as the
  original's do in their `state_info` (`beta/samplers.py:1009-1010`). It is
  the one entry of that state a converted node reads (`LatentUpscaleWithVAE`,
  below). V2 keeps it in a marker key of its own (`latent_chain.py`):
  `{"node": "ClownsharKSampler_Beta", "denoised": <tensor>}`. The tensor is
  the original's `state_info["denoised"]`, bit for bit (`tests/v2_parity.py`).
  When the loop runs no step, the original's state is the incoming latent's.
  The marker then carries the incoming marker's estimate, or none.

## Options and value nodes

- `SharkOptions_Beta`, `ClownOptions_DetailBoost_Beta` and
  `ClownOptions_SigmaScaling_Beta` copy the original bodies. An OPTIONS value
  is a dict. Its tensor entries cross between nodes as tensor refs, so the
  sampler receives the original's values and dtypes. An unlinked SIGMAS
  input of `ClownOptions_SigmaScaling_Beta` is stored as None, as there.
- `ClownsharKSampler_Beta` applies OPTIONS the way the original does. Each
  option is read in three places: the sampler node, its advanced sampler
  stage and its noise stage. The node mirrors those reads, in order, for:
  - its own OPTIONS output (chained into a later sampler);
  - `SharkOptions_Beta`'s keys;
  - `ClownOptions_DetailBoost_Beta`'s keys;
  - `ClownOptions_SigmaScaling_Beta`'s keys: the SDE noise scales
    (`s_noise`, `s_noise_substep` and their per-step lists), `noise_anchor`,
    and the schedule factors `d_noise` and `d_noise_inv` with their start
    steps. The loop applies the factors itself, so the model is evaluated at
    the rescaled sigmas, as in the original. The node's check for the final
    sigma_min step (below) follows the same rescaling.
- Any other OPTIONS key is refused by name before sampling. So are:
  - SDE noise types other than gaussian;
  - channelwise CFG;
  - the `brownian` init noise, which needs core's Brownian-tree sampler;
  - the `wavelet` init noise when the guest runtime lacks PyWavelets;
  - noise-scaling cycles other than 1;
  - non-zero noise boosts;
  - a `d_noise` or `d_noise_inv` that is not finite and positive. The loop
    would evaluate the model at negative or non-finite sigmas, which the host
    refuses.
- At the pinned commit, the DetailBoost methods `sampler_substep` and
  `sampler_substep_normal` fail inside the original's sampling loop. V2 runs
  the same loop and fails the same way.
- `TextBox1` and `SetImageSizeWithScale` return what the original returns.
  `Sigmas Power` raises the exact input schedule to the power in its own
  dtype; infinities from zero sigmas pass on, as in the original.

## Text, size, sigma and image nodes

- `TextBox2`, `TextConcatenate`, `SetImageSize` and `SeedGenerator` return
  what the original returns. An unlinked `TextConcatenate` text is the empty
  string, as there.
- `Sigmas Mult` multiplies the exact input schedules as the original does,
  `sigmas * sigmas2 * multiplier`, in torch's own dtype promotion.
- `Frame Select` selects the frame `frames[select]` on the host
  (`image.select_batch`), as `Frames Slice` does; an index past the batch
  fails with the original's IndexError.
- `Image Repeat Tile To Size` runs the original's body on the exact input
  pixels: tile, then crop, or resize with upstream's `image_resize` (stretch,
  lanczos).
- `EmptyLatentImageCustom` builds the original's zeros: shape, channels,
  ratio and precision as there.
- The sigma nodes run upstream's own classes, copied verbatim from
  `sigmas.py` into `res4lyf_core/sigmas_values.py` and
  `res4lyf_core/sigmas_resample.py`, on the exact input schedule in its own
  dtype. Empty and non-finite schedules pass on as the original passes them.
- `Film Grain` and `Image Grain Add` run upstream's own classes, copied
  verbatim from `images.py` into `res4lyf_core/images.py`, on the exact input
  pixels.
- `Frames Slice` selects the same frames as the original's
  `frames[start:stop]`, on the host (`image.select_batch`), so its pixels never
  enter the guest.
- `VAEEncodeAdvanced` follows the original's `main` line for line. It resizes
  with upstream's own `image_resize` (whose `lanczos` is Core's, copied
  verbatim) and encodes on the host with Core's `vae.encode`.
- `LatentUpscaleWithVAE` follows the original's `main`
  (`helper_sigma_preview_image_preproc.py:618-691`), with these steps:
  - It decodes on the host with Core's `vae.decode`. The original decodes the
    estimate a RES4LYF sampler's latent carries in its `state_info`; V2
    decodes the one the V2 sampler's marker carries (the same tensor). Without
    either, both decode the samples.
  - `vae.decode_tensor` applies the original's 5-D to 4-D reshape.
  - It resizes with upstream's `image_resize` (stretch, lanczos), encodes on
    the host with Core's `vae.encode`, and returns a copy of the input latent.
    The new samples are in the input samples' dtype. Where a marker came in,
    it carries the new latent as its estimate, as the original's `state_info`
    does.
  - A latent carrying an unconverted sampler's `state_info` is refused by
    name.
- Copied upstream code: `res4lyf_core/VENDOR.json` records each copied
  definition's source lines and sha256. `vendor_res4lyf.py` also proves from
  the source text that every global name a copied definition uses resolves
  as it does upstream (`tests/test_res4lyf_vendor.py` reruns it in the gate).

## Reduced envelope (refused by name, never approximated)

At queue time (`validate_inputs`):
- `sampler_mode` other than `standard`. Unsample and resample continue another
  sampler's saved state, which a V2 latent cannot carry.
- Methods that need more than 3 model evaluations per step. The admitted list
  is frozen from the original's own tableaus (`_clown_frozen.json`).
- Spellings that name no method, or that run a method in a different
  implicit/explicit mode from its menu entry.
- A negative `cfg` (channelwise CFG needs a post-CFG model patch).
- `seed` -1.
- These fail in the original itself: `denoise` 0, `kl_optimal` with 1 step,
  and `bong_tangent` with 1 step.

At run time:
- `guides`, and OPTIONS outside the set above.
- A missing model, latent, positive or negative input.
- Latent fields other than `samples`, `noise_mask` and `batch_index`, such as
  another sampler's saved state.
- Latents that are not 4-D.
- Models the guest cannot confirm:
  - flow-parameterized models must be plain flow models;
  - sigma-parameterized models must be in the SD1/SDXL families;
  - for these, schedules that end on the model's `sigma_min` are refused. There
    the original applies the model's own `calculate_denoised`, and the guest
    cannot tell EPS from V-prediction.
- Schedules that are not finite, non-negative and non-increasing.
- Upstream code paths that need unconverted Core code (for example nested
  tensors, Brownian-tree noise or packed latents). These refuse with their
  own name.

## Known differences

- Output latents: `samples` and `noise_mask` are exact. In place of the
  original's `sampler`, `guider` and `state_info` entries, V2 adds its own
  marker, carrying the loop's final denoised estimate (exact, see above).
  The rest of the original's entries are host objects and loop state that a
  V2 latent cannot carry. RES4LYF's continuation modes need them, and they
  are refused. Core's nodes pass the marker on, or drop it, exactly where they
  pass on or drop the original's `state_info`, and otherwise behave the same
  with it as without it (`tests/test_chain_key_core.py`).
- Queue-time checks for the seven widgets that `validate_inputs` names
  (sampler, scheduler, steps, cfg, seed, sampler mode, denoise):
  - V2 applies Core's own bounds and lists, including the original menu's
    acceptance of sampler names with or without their folder;
  - refusals use the pack's wording and arrive as custom validation errors.
- Menus are frozen copies of the original's lists on the conversion core.
  Choices that other installed packs add at runtime are not mirrored.
- Live previews show the model's latest denoised estimate. Final outputs are
  not affected.
- The original options nodes update the incoming OPTIONS dict in place, so
  other consumers of that upstream output also see the change. V2 gives each
  node its own copy. The returned dict has the same entries in the same order.
- `ClownOptions_DetailBoost_Beta` builds its tables on a CUDA device in the
  original, so it fails on a CPU-only host. V2 builds the same float64 values
  on the CPU. The sampler moves them to the latent's device in both cases.
- Cancelling during sampling (platform limitation): on the current platform,
  an interrupt raised while the guest's loop waits on a model evaluation does
  not reach the run. The run hangs until the platform retires the guest. A
  transport fix is pending. Nothing carries over: the next run starts a fresh
  guest and is exact.
- Verified on CPU. Equality of the init noise on GPU hosts is still to be
  confirmed.
- Random draws (`Film Grain`, `Image Grain Add`, and `Sigmas Resample`'s
  "model" mode): upstream draws from torch's process-wide generator and never
  seeds it. In the original that is the host process's generator, so the draws
  continue whatever state earlier nodes left there (Core's sampler seeds it in
  `prepare_noise`, for example). In V2 they continue the guest's own
  generator, so the grain differs between the two even within one prompt.
  Given the same generator state, both give the same result. On a GPU host the
  original draws Film Grain's noise on the GPU; V2 draws on the CPU. With more
  than one thread, upstream's grain is not repeatable even for a fixed state:
  one indexed assignment writes many values to random positions, and which
  value a repeated position keeps depends on thread timing. V2 runs the same
  code and behaves the same way.
- `VAEEncodeAdvanced` seeding: the original calls `torch.manual_seed(42)` and
  `torch.cuda.manual_seed_all(42)` before encoding
  (`helper_sigma_preview_image_preproc.py:257-258`); V2 does not. Core's image
  VAEs encode deterministically (the KL posterior's mode), so the latents are
  the same either way. The observable effect: after the original node runs,
  the host's global generator restarts from seed 42, so a later node in the
  same prompt that draws from the unseeded global generator gets the numbers
  that follow seed 42 there, and different numbers in V2.
- `VAEEncodeAdvanced` with interpolation `lanczos` (the default): Core's
  `comfy.utils.lanczos` returns channels-first memory, so the original hands
  `vae.encode` a channels-first view of the resized pixels. A V2 image crosses
  to the host as a contiguous buffer. The pixels are bitwise equal, but Core's
  encode rounds its convolutions differently for the two memory layouts, so
  the latents differ in the last bits (on the test fixtures, at most 3.1e-5
  absolute). V2's latents are bitwise equal to Core's encode of
  the same pixels in contiguous layout, which is what Core's own VAE Encode
  node gives for them. The other interpolations hand over contiguous pixels in
  both versions and are bitwise equal. Platform ask: a layout-preserving host
  resize (an `ImageRef.resize` that runs Core's `common_upscale` on the host,
  so the pixels never cross before the encode) would make these latents
  bitwise equal as well.
- `LatentUpscaleWithVAE` has the same two differences as `VAEEncodeAdvanced`:
  - The original seeds torch's process-wide generator with 42 before decoding
    (`helper_sigma_preview_image_preproc.py:653-654`); V2 does not. The
    latents do not depend on it. The host's generator is left where it was.
  - Its interpolation is always `lanczos`, so its latents fall in the
    layout-rounding class above. The pixels are bitwise equal. The latents are
    bitwise equal to Core's encode of those pixels in contiguous layout.
  - In addition, with `state_info` the original also decodes, resizes and
    re-encodes the loop's history (`data_prev_`) into its output state. Only
    the refused continuation modes read that history, so V2 carries none.
- Image outputs cross to the host as contiguous buffers. Where the original
  returns a strided view (`Image Repeat Tile To Size` crops a tiled view and
  its lanczos path returns channels-first memory), the pixels are equal, and
  a later VAE encode of them can round as described for `VAEEncodeAdvanced`.
- `EmptyLatentImageCustom`: the original allocates its zeros on Core's
  intermediate device, which is the CPU unless the host runs GPU-only. A V2
  latent is the host's copy of the guest's zeros.
- `Frames Slice`: an empty slice (`start` at or past the batch size, or not
  below `stop`) is refused by name. The original returns an empty image
  batch, which a V2 image cannot hold. The host's batch selection takes
  images with 1, 3 or 4 channels.
- Image outputs are finite and hold at most 4096 images (V2 images).
  `Film Grain` refuses by name when `repeats` would exceed that.
- Guest runtime: the pack declares a dependency profile in `pyproject.toml`
  (exact pins: einops, scipy, tqdm). The manifest's runtime block names the
  profile built from those pins (`profile_sha256` b90d9207…), so a production
  guest gets exactly these modules. The ClownsharKSampler_Beta loop needs
  einops and tqdm when its module is imported. The beta57 scheduler needs
  scipy when it runs, and so does `Sigmas Resample` (its copied code imports
  scipy at module level, as upstream's `sigmas.py` does; only an unreachable
  method uses it). numpy, torch and mpmath come from the guest base. Every
  other node, and every refusal, needs only torch, numpy, Pillow and the SDK,
  so they load with or without the profile (`tests/test_profile_load.py`).
  pywt is optional: without it, wavelet noise types are refused by name.

## Verification

All tests run on CPU without weights, on seeded tiny synthetic models (EPS
and flow) and seeded synthetic VAEs. No checkpoints, workflows or media are
used. Each test runs as a plain gate run with the pack root at `/pack`; extra
mounts are optional (the original's heavy imports that the gate lacks become
labelled import stubs, which the compared paths never use). The V2 side runs
in real guests started through `tests/_res4_sealed_guest_entry.py`, whose
import audit refuses any import by pack code outside the standard library,
the sealed guest lock (`tests/guest_lock_modules.json`) and the declared
profile.

- `tests/test_res4lyf_schemas.py`: every node's node info, in process and as
  served from the manifest, against the original's.
- `tests/v2_parity.py`, with `tests/ref_original.py` and `tests/cases.py`:
  - the original against V2 in a real guest, compared bitwise;
  - queue-time validation against Core's own checks on the original;
  - Core's `calculate_sigmas` through the scheduler providers against the
    original's registration;
  - cancellation and recovery;
  - model evaluations per pass;
  - a negative control.
- `tests/v2_parity.py` also runs the sampler fed by OPTIONS chains that the
  options nodes build in the guest, against the original's chains. It
  compares the option dicts and the outputs bitwise. On both output latents
  it compares the marker's estimate with the original's
  `state_info["denoised"]`, bitwise.
- `tests/test_res4lyf_upscale.py`: `LatentUpscaleWithVAE` against the
  original on the TAESD and KL VAEs:
  - plain and chained latents, sizes up and down, batches, masks and other
    keys, half-precision samples, and the failure when no estimate was
    stored;
  - the layout-rounding check above;
  - the seed: results with the generators moved, and the generator side
    effect;
  - a negative control.
- `tests/test_chain_key_core.py`: every core node that takes a LATENT and
  can run on synthetic inputs, run three ways: with a plain latent, with the
  V2 marker, and with the original's `state_info`. Outputs, UI data and
  written files must be equal once the extra key is set aside. The marker must
  be passed on exactly where `state_info` is.
- `tests/test_res4lyf_simple.py`: the value, sigma, image and latent nodes
  (all but `VAEEncodeAdvanced` and `LatentUpscaleWithVAE`) against the
  original, every option, edge values and failures, and the named refusals. The random nodes are compared with both sides seeded
  identically. Two negative controls (a 1-ulp change, a different seed).
- `tests/test_res4lyf_vae.py`: `VAEEncodeAdvanced` against the original on a
  TAESD and an SD-style KL VAE: every option, inputs present and absent, the
  seed (latents equal with the generators moved; the generator side effect
  checked) and the `lanczos` layout difference above.
- `tests/test_res4lyf_vendor.py`: the copied upstream code re-derived from
  the pristine pack and compared byte-for-byte; Core's `lanczos` copy.
- `tests/encode_manifest.py`: manifest regeneration and loader check (every
  id, the validation signatures, the scheduler providers).
- `tests/test_production_load.py`: every manifest row resolved the way the
  guest resolves it: only the row's module is imported, without the pack's
  `__init__.py`, and the class is looked up by its manifest name. Checked in
  process and through a real guest.
- `tests/test_profile_load.py`: maps which nodes need the dependency profile.
  Every node and both schedulers then run in a real guest that can import the
  profile's modules only from the mounted profile wheels: once with them
  (everything loads), once without them (only the mapped nodes fail).
- `tests/test_core_ids.py`: loads core's own nodes (`nodes.py`,
  `comfy_extras`, `comfy_api_nodes`) and checks that the manifest registers
  none of their ids, and that every id the pack leaves to core
  (`_frozen_nodes.json`, `meta.core_owned`) is one that core registers.
- `tests/freeze_all.py` and `tests/freeze_clown.py` capture the frozen schemas
  and lists from the original. The ids core registers itself are then left
  out (`meta.core_owned`).
