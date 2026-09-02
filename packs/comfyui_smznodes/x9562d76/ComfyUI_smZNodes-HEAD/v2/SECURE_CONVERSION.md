# ComfyUI_smZNodes Secure Nodes V2 conversion

Source: `https://github.com/shiimizu/ComfyUI_smZNodes` at
`9562d76c3cf206a3c2362e2baf8bbf717a4869a5` (snapshot key `x9562d76`).

## Census and terminal ledger

The pinned source exports exactly two backend IDs and registers exactly two
frontend extensions. It also installs prompt/sampling behavior that is not a
node registration.

- Backend: 0 supported, 0 rejected, 2 pending.
  - `smZ CLIPTextEncode` — **pending**. Its ordinary `comfy` path, CLIP-L/G
    `comfy++` path, six pack parsers, prompt schedules, mean-normalized
    emphasis, BREAK chunking, and SDXL base micro-conditioning are converted.
    The node fails closed for the remaining valid features listed below.
  - `smZ Settings` — **pending**. The exact wildcard identity and all pinned
    widget IDs remain. It is an unchanged pass-through at upstream defaults,
    and non-default values which depended on sampling/noise hooks fail closed.
- Frontend: 1 supported, 0 rejected, 1 pending.
  - `Comfy.smZ.dynamicWidgets` — **supported** through one additive
    `comfy.defs.extend` registration. Widget visibility and menus use handles;
    wildcard socket behavior is native and no graph/renderer prototype is
    changed.
  - `Comfy.smZ.WorkflowImage` — **pending** through one bounded JPEG workflow
    importer. JSON API prompts and baseline A1111 text-to-image parameters are
    supported. Hires graphs and fuzzy installed-model/embedding resolution are
    still gaps, and fail rather than being silently flattened.
- Non-node intent: 0 supported, 0 rejected, 2 pending.
  - downstream sampler-step discovery for `smZ_steps` — **pending**;
  - sampling/noise/CFGDenoiser transforms selected by Settings, including the
    named sampler `dpmpp_2m_alt` — **pending**.

The old mechanisms are rejected, not the valid intent: no process-global core
replacement, PromptServer prompt rewrite, sampler-enum mutation, caller-frame
rewrite, runtime package installation, module reload, web-directory copy, or
ambient network retrieval is restored.

## Exact supported prompt paths

The A1111 schedule grammar and emphasis arithmetic remain pack-side in
`modules/text_processing`. CLIP token IDs and component embeddings arrive over
the typed `ClipRef` operations; tensor values cross only through the declared
`raw` capability. Pack-created conditioning uses `CondRef.from_value` only for
the embedding row and pooled output. Schedule windows and SDXL size fields use
the closed `CondRef.with_timestep_range` and `CondRef.with_metadata`
transforms, not arbitrary annotation bags.

The following gaps are deliberate and precise:

- weighted-parser textual inversion needs the embedding vectors in the guest;
  `ClipRef.tokenize` can return a host-precomputed embedding token, but the
  component encoder seam accepts integer IDs only. The native `comfy` parser
  remains available.
- T5/Gemma weighted parsing needs a bounded component-encoding primitive for
  that component. The current operation is closed to CLIP-L and CLIP-G.
- `use_old_emphasis_implementation` needs a complete tokenizer vocabulary plus
  token-to-string conversion to reconstruct bracket-token multipliers. Neither
  is exposed.
- SDXL Refiner and other CLIP-G-only families have the same published token
  component shape. Applying refiner aesthetic metadata safely needs a bounded
  CLIP family/class tag; the node cannot infer it from private host objects.
- weighted `AND` uses the pack's composable-diffusion CFG equation. Core
  conditioning `strength` has a different normalization and is not substituted.
- automatic `smZ_steps` needs bounded downstream traversal from the current
  node to a sampler. The existing graph operation only projects the directly
  linked producer. The explicit optional input remains fully supported.

## Settings audit at the pin

Every option was traced from `smZ_Settings.apply` into the pinned source.

Actually consumed:

- `enable_emphasis`, only inside the unavailable old-emphasis implementation;
- `RNG` and `ENSD`, by the global `prepare_noise` replacement after an smZ
  encoder copied Settings stored on a CLIP into the process-global options;
- `eta`, `s_churn`, `s_tmin`, `s_tmax`, and `s_noise`, by the global sampler
  wrapper;
- `skip_early_cond`, `NGMS`, and `NGMS all steps`, by the global sampling
  function;
- `sgm_noise_multiplier`, by the global `Sampler.max_denoise` replacement;
- `debug`, for pack logging.

Inert at this exact pin (stored but never read by an active path):

- `Prompt word wrap length limit` (the active classic engine hard-codes `20`);
- `disable_nan_check`, `upcast_sampling`, `pad_cond_uncond`, and
  `batch_cond_uncond`;
- `Use previous prompt editing timelines` (the encode call never forwards the
  stored value);
- `Use CFGDenoiser` (selection is driven by composable-conditioning weights,
  not this option).

The inert controls are retained for workflow compatibility and are not claimed
to do anything. Sampling options at their pinned defaults pass through because
they do not change core behavior. Carrier behavior at this pin was asymmetric:
`eta`/`s_*`, skip/NGMS, and `sgm_noise_multiplier` were read from MODEL
`model_options`; `RNG`/`ENSD` stored on MODEL were inert. Conversely,
`RNG`/`ENSD` on CLIP reached the global noise hook through the smZ encoder,
while those MODEL sampler parameters stored on CLIP were inert. Each
non-default value fails with its name only on the carrier where upstream
actually consumed it. Other wildcard values returned before options were
consumed. The node does not attach a broad options dictionary to a model or
CLIP.

## `dpmpp_2m_alt` evidence and smallest gap

The source is DPM++ 2M except for one state update after every nonterminal
step: `old_denoised = denoised * (1 + 0.15 * (i / len(sigmas)) ** 2)`. That
modified previous denoised value changes the second-order update on subsequent
steps. The recurrence is preserved pack-side in `sampler_programs.py`. The
differential test evaluates it against the pinned function and plain DPM++ 2M,
proving exact parity with the former and later divergence from the latter.

There is no existing exact closed path: `dpmpp_2m_alt` is absent from the
current core sampler names, and `SamplerRef.named` rejects names outside that
list. The final `ClosureRef.wrap_sampler` seam was audited too. It accepts only
a `model_sigma` closure and then delegates to the named sampler's unchanged
recurrence. Sigma remapping cannot reproduce scaling only the cached previous
denoised value. The differential includes a sigma-invariant nonlinear model,
for which every model-sigma remap is unobservable but the alternate recurrence
still diverges, so `wrap_sampler` is demonstrably insufficient.

The shipped `custom_sampler` closure is the correct invocation contract for the
algorithm: one pack-owned loop receives only latent/sigmas plus the bounded
denoise/preview broker, and the invocation capability and transferred buffers
expire when it returns. It still does not make this non-node registration
reachable. A `ClosureRef` can be retained only during a node dispatch, while
the pinned source contributes a globally selectable sampler name at pack load;
a prompt-scoped closure cannot create that catalog entry. Inventing a third
node or overloading `smZ Settings` would change the exact source census and
workflow semantics, so `dpmpp_2m_alt` remains pending.

The smallest remaining generic gap is a declarative sampler-provider registry,
analogous to the D22 scheduler providers. A sealed manifest entry would name a
pack-relative program and public sampler name; host collision preflight would
own catalog registration. The provider manager would own a per-pack guest and
lifetime outside node dispatch, and each sampler run would use the existing
`custom_sampler` invocation broker with its fixed sigma/step, sequential-op,
shape/dtype/device, timeout, and capability-expiry bounds. This adds no general
callback, arbitrary ref access, or pack mutation of the host sampler table.

## Frontend boundary

The host chooses the JPEG and projects at most 16 MiB into the sandbox. The
pack parses bounded EXIF/TIFF structures and returns workflow data. It never
sees a path, credential, application singleton, DOM belonging to the host, or
network authority. PNG/WebP loading remains with core. A filename containing a
URL is just a filename; it is never retrieved.
