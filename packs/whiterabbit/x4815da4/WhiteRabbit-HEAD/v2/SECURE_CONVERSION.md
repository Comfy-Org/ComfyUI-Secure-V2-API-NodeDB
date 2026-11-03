# Secure Nodes V2 conversion ledger

- Pack: `whiterabbit`
- Upstream: https://github.com/Artificial-Sweetener/WhiteRabbit
- Pinned commit: `4815da41473c99400da6ca4127f0e324dbfd865a`
- Release: `x4815da4`
- Backend: 14 supported, 0 rejected, 0 pending
- Frontend: 0 registrations
- Routes and other runtime registrations: 0

## What these nodes do

WhiteRabbit is a video utility pack. Five nodes arrange or trim frame batches,
two score and crop loop seams, four run RIFE frame interpolation, one holds
pixels across a sequence, one resizes batches with Lanczos filtering, one
applies a selected watermark, and one runs a ComfyUI upscaler with explicit
tiling and memory-layout controls.

All image, video, loop-scoring, watermark-compositing, RIFE, and Lanczos
algorithms remain pack-side. The guest receives raw image or mask tensors only
for nodes whose defining behavior is tensor math. It never imports ComfyUI,
reads an ambient filesystem path, starts a process, or performs network I/O.

## Host boundaries

- RIFE checkpoints are four immutable, revision- and SHA-256-pinned weight
  declarations. The host downloads and safely parses their tensors; the RIFE
  architectures and inference stay in the sandbox.
- `torchlanc==1.1.1` is supplied through the content-addressed admitted-pack
  dependency profile. The dependency is not installed from the network at
  execution time and cannot replace a common or trusted runtime package.
- A watermark name resolves through the managed input asset catalogue. Only
  bounded bytes cross to the guest; a host path never does.
- The advanced upscaler uses the typed `UpscaleModelRef`. Its optional tile
  size and channels-last flags are host-owned because the model remains on the
  host; omitting those options still uses the pre-existing direct upscale path.
- Optional frame-interpolation state uses `InterpolationStatesRef.skip_mask`.
  The host projects only a bounded list of per-pair booleans, so the pack can
  skip the same frame pairs without receiving the foreign extension's live
  Python object or invoking its methods.

These last two boundaries are documented as D25 and D26 in the V2 Python API
decision log. They exist for the concrete WhiteRabbit nodes above; neither is
an arbitrary model-call or object-introspection API.

## Verification

`backend/tests/test_whiterabbit_pack_conversion.py` pins the source tree,
complete 14-node census and schemas, manifest, dependency profile, four weight
identities, reachable guest import closure, and absence of host imports. It
also runs every node ID in a real managed guest with a distinct PID, exercises
the real admitted `torchlanc` wheel, safely loads the real pinned RIFE 4.7
checkpoint and performs interpolation, and checks the managed watermark and
advanced upscaler boundaries. Core SDK tests separately pin the bounded
interpolation-state projection and tiled-upscaler fallback behavior.

The pristine sibling remains byte-identical to the pinned upstream tree. The
V2 conversion retains the upstream AGPL-3.0 license and the existing MIT notice
for the adapted ComfyUI-Frame-Interpolation architecture.

## Repair r1

- **Class names.** The eight pure-binding classes (`PrepareLoopFrames`, `AssembleLoopFrames`, `RollFrames`,
  `UnrollFrames`, `TrimBatchEnds`, `AutocropToLoop`, `PixelHold`, `BatchResizeWithLanczos`) are also
  bound under their generated names (`...Secure`), which is how `secure-nodes.json` imports them.
- **Watermark menu.** `secure-nodes.json` holds the watermark menu as it was when the pack was converted
  (empty), so core refused every file. `BatchWatermarkSingle` now checks the value itself against the
  original's list, the input folder's images (`WatermarkFileResolver.choices`), read through the SDK
  when the prompt is validated. A missing file gets core's "Value not in list" text.
- **Dependency profile.** `runtime.dependencies.profile_sha256` is the one the reference deployment
  resolved for `torchlanc==1.1.1`.

## RIFE checkpoints: the two pickle menu entries load their registered SafeTensors conversions (repair NED r2)
- The RIFE menus keep upstream's four names. `rife47.pth` and `rife49.pth` are pickles, which the engine's asset
  guard does not load. Each is now declared as its registered SafeTensors conversion (`rife47.safetensors`,
  `rife49.safetensors`: tensor-equal state dicts under the same tensor names), so selecting either name loads the
  same tensors through the same brokered asset path. `rife_v4.25.safetensors` and `rife_v4.26.safetensors` are
  unchanged.
- The menu names are bound to their declarations explicitly (`_RIFE_BY_NAME`); a name is never inferred from a file
  name. The architecture is still chosen from the menu name, as before.
- `secure-nodes.json`: in the four RIFE rows, the two `required_weights` entries change accordingly; nothing else in
  the manifest changes.
- `tests/test_rife_converted_weights.py` checks the declarations, the menu binding, the manifest rows against the
  real encoder, and the load path (with stand-in tensors: the request, the asset and the strict state-dict load).
