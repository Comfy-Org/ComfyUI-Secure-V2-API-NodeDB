> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 64 of 64 converted; 52 tested (scoped), 3 converted but untested/partly tested,
> 9 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> (Revision 2. The 14: 11 pending capability — `addict` ×4, `yacs` + >4 GiB ×1, transformers bundle constructor ×6; 3 blocked by the platform — FaceMesh: legacy mediapipe API absent on Python 3.13; MeshGraphormer ×2: engine image lacks libEGL/libGLESv2.)
> **Revision 3 (2026-10-21, docs only): 8 nodes counted as tested refuse on live.** These are DepthAnythingV2, DWPose,
> AnimalPose, DensePose, LeReS, MiDaS Depth and Normal, and Unimatch. Their published model selections are unapproved, so
> each raises a selection error before loading anything (request #21). See "Revision 3".
> **Revision 4 (2026-10-21):** UniFormer, SemSeg and Metric3D Depth/Normal are tested (scoped) under a test-only approved
> selection and a test-env `addict` (51 tested, 10 open). Live: the 24 tested nodes that declare required weights are
> refused at dispatch first (request #23). See "Revision 4".
> **Revision 5 (2026-10-21):** DiffusionEdge is tested (scoped) under a test-only approved selection and a test-env
> `yacs` (52 tested, 9 open). Live: it refuses 'selection pending' until request #21, then needs `yacs` (request #25)
> and operator staging of all four weight files (about 2.1 GB). See "Revision 5".
> **Revision 6 (2026-10-21):** the review follow-ups are fixed in code (restricted-decode hardening for UniFormer,
> Metric3D and DiffusionEdge) and re-tested exactly on the a2 base. No count or live gate changes. See "Revision 6".
> **Revision 7 (2026-10-21):** DiffusionEdge's urban and natrual environments are inspected and tested (scoped) on the
> revision 6 bytes. No count or live gate changes. See "Revision 7".
> **Revision 8 (2026-10-21):** Metric3D's vit-large backbone runs (a 2 GiB per-checkpoint budget) and is tested for
> both nodes. vit-giant2 still refuses, and that refusal is now tested. No count or live gate changes. See "Revision 8".
> **Revision 9 (2026-10-22):** the shared restricted zip proof now scans a checkpoint's `data.pkl` only when it is
> byte-identical to the record torch itself decodes (review A-L1). No count or live gate changes. See "Revision 9".
> **Revision 10 (2026-10-22):** the review-N1 follow-up is tested — an ordinary mismatched-name archive is accepted
> by the revisions 1-8 helper and refused by revision 9. Docs only; no count or live gate changes. See "Revision 10".

# ControlNet Aux — secure conversion report (in progress, revision 10)

## Provenance

- Upstream: https://github.com/Fannovel16/comfyui_controlnet_aux
- Pinned commit: `0cd290477128d42cdc3e76a826a402d866e8c684` (key `x0cd2904`)
- Revision 2 = the committed revision-1 tree plus the published-v2 fixes of the families that passed since (listed below). Test-only selection approvals are NOT included: production admission stays closed.
- Mirror mode: original node ids, display names and categories; no `-Secure` suffixes.

## Revision 10 (2026-10-22): the A-L1 differential is tested (review N1)

Revision 10 is docs only. It records that the review's N1 follow-up now has evidence: the record difference revision 9
refuses is demonstrated with an ordinary archive, not just argued from source.

Evidence (`validation/20261022-controlnet-aux-al1-n1-a2base-r1/`):
one bounded attempt on the a2 base (no weights, no selection; CPU, one thread, 3 GiB; torch 2.8.0+cu128; peak 1.32 GB; a
few seconds). It mounts two helpers straight from git — the pre-A-L1 helper (`af7b3018`, revision 8) and the published
revision 9 helper (`2cecd6a4`) — and compares them:
- a `torch.serialization` spy shows the reader `torch.load` uses is exactly `torch.PyTorchFileReader`, read once, and
  `torch_record` equals its `data.pkl` bytes;
- a mismatched-name archive built with ordinary `zipfile.writestr` (stored records `archive/version`, `archive/Data.pkl`
  and `x/data.pkl`): Python's `zipfile` selects `x/data.pkl` (sha256 `a16197da…`), while torch resolves
  `get_record('data.pkl')` case-insensitively under the first entry's directory to `archive/Data.pkl` (sha256 `ccf5c07c…`).
  **Revisions 1-8's helper would have accepted this archive** (it scans whatever `zipfile` selects); **revision 9 refuses
  it**, because the bytes torch decodes are not the bytes it scanned. The refusal text is
  "restricted torch archive data.pkl differs from the record torch decodes";
- a plain `torch.save` archive is accepted by both helpers (control).

This closes the N1 follow-up from the A-L1 review. **The pinned checkpoints were never affected:** every converted
family's weights are sha256-pinned, so a mismatched-name archive cannot be substituted for a real checkpoint. This is a
defence-in-depth tightening of which record the proof scans, not a fix to any observed acceptance of a real checkpoint.

Live: unchanged. Counts: unchanged (52 tested (scoped), 3 converted but untested/partly tested, 9 partial or missing).

## Revision 9 (2026-10-22): the restricted zip proof scans only torch's own record (review A-L1)

Revision 9 closes the A-L1 residual carried since revision 6. The shared zip proof now scans a checkpoint's `data.pkl`
only when the bytes it selected are byte-identical to the record torch itself decodes, so Python's `zipfile` and torch's
miniz can never disagree about what is scanned.

Change (production code; independently reviewed):
- `_restricted_globals.py`: `checkpoint_pickle_globals` still selects the single, bounded, STORED `data.pkl` with
  `zipfile` (L1-L3 unchanged), then reads those bytes and requires them to equal `torch_record(payload)` - a new
  module-level helper returning `torch._C.PyTorchFileReader(payload).get_record('data.pkl')`, the record `torch.load`
  unpickles. It scans (`get_globals_in_pkl`) only on a match; a difference is one new refusal, and a read or scan error
  stays the existing clean refusal. `require_default_allowlisted` is unchanged. The four parser differences the residual
  named (the case-insensitive lookup, the central-directory discovery, NUL-truncated names, the Info-ZIP Unicode path
  field) now reduce to one behaviour: torch's bytes differ, so the proof refuses, whichever difference it was.

Evidence (`validation/20261022-controlnet-aux-al1-a2base-r1/`):
one selected bounded attempt on the a2 base (the revision 6-8 bytes plus this change), no node run: CPU, one thread,
8 GiB; torch 2.8.0+cu128; peak 2.89 GB; about 8 s of helper checks after the runtime import.
- Anchors: a `torch.serialization` spy showed `torch_record` returns exactly the bytes `torch.load` reads for `data.pkl`,
  on a fresh `torch.save` archive and on one real checkpoint (equal sha256 on both sides). An injected differing record
  was refused with the new text; the "no decode" guarantee is that each family's selection refuses before its own
  `torch.load` line (the review confirmed this), which the injected row illustrates with a zero scan and decode count. An
  injected read failure gave the existing clean refusal. A fresh archive is still accepted and scanned (positive control).
- The three families on the patched helper: the genuine UniFormer, Metric3D vit-small and DiffusionEdge main and swin_b
  checkpoints were each accepted with their published pinned globals and decoded under `weights_only`; main's pre-fix
  helper accepted them identically. Each file was pinned by sha256, and the pinned globals equalled the `data.pkl` scan.

A known gap and a test follow-up (before #21) are in the residuals list: the second read is torch's own and is not
separately bounded, and the spy check plus a mismatched-name archive should be added next round (revision 9 review N1, N2).

Live: unchanged (requests #21, #23, #24 and #25, and operator staging of the undeclarable weights). The families stay
gated on an approved selection (#21); this change only tightens which record the proof will scan.

Counts: unchanged (52 tested (scoped), 3 converted but untested/partly tested, 9 partial or missing).

## Revision 8 (2026-10-21): Metric3D vit-large (2 GiB per-checkpoint budget)

Revision 8 lets Metric3D's vit-large backbone run, and tests it for both nodes. The dropdown of both nodes offers
vit-small, vit-large and vit-giant2, as upstream does (vit-only). Before this revision, only vit-small fitted the
selection code's 512 MiB limit.

Change (production code; independently reviewed with revision 6: CLEAR_WITH_NOTES, no high or medium findings):
- `_metric3d/selection.py`: the archive bytes, the declared tensor bytes and the decoded total share a 2 GiB
  per-checkpoint budget, as for DiffusionEdge. The archive was already read in bounded read_range chunks, so the guest's
  whole-read cap does not apply. The primitive metadata proof keeps its own 512 MiB bound. Only `validate_raw` and the
  constants change, and every refusal text is the same.

| Backbone | Checkpoint (JUGGHM/Metric3D @ 80d2d141) | Bytes | Outcome |
| --- | --- | --- | --- |
| vit-small | `metric_depth_vit_small_800k.pth` | 150,120,967 | tested (revision 4) |
| vit-large | `metric_depth_vit_large_800k.pth` | 1,647,972,663 | tested (this revision): fits the budget |
| vit-giant2 | `metric_depth_vit_giant2_800k.pth` | 5,510,989,187 | refused at selection time, before any read (tested in this revision) |

Evidence (`validation/20261021-controlnet-aux-metric3d-large-a2base-r1/`):
two selected bounded attempts, one per node, on the a2 base, with the revision 6 bytes plus this change. Sandbox off, CPU,
one thread, 8 GiB; peak 6.44 GB; 281 s (Depth) and 275 s (Normal).
- Inspection, in each attempt:
  - the pins, the zip format and 3 default-allowlisted globals;
  - three identical decodes;
  - Metric3D's raw facts, computed as `validate_raw` checks them: one `model_state_dict`, 529 tensors,
    1,647,769,708 B.
  The test-only approved selection derived from these facts (the revision 4 vit-small selection plus vit-large) was
  accepted by the validator in both attempts, with the same hash. The evidence holds it byte-exact.
- Parity, per node:
  - the pack as published refuses with its own text;
  - the genuine original, an ordinary guest and the registered node in process are exactly equal on the revision 4
    input (checker 64x64, resolution 64, fx = fy = 1000);
  - the sealed read is reached, and the original's checkpoint path is the selection's discriminator;
  - the guest without `assets` is refused.
  Each vit-large call took about 85-90 s on one CPU thread.
- vit-giant2, in the Depth attempt: an approved giant2 entry carries the real file facts, taken from the Hugging Face tree
  metadata (the file was never fetched). The node refuses with "Metric3D bounded archive count is unselected" at
  selection time, with no sealed read and no vendor import.
MERVYN fetched vit-large from the pinned revision, in one attempt, with size and sha256 from the tree metadata.

Live: unchanged (requests #21, #23 and #24). Each backbone used on live needs its facts in the production selection (#21).
vit-large is not a declared weight. On live, the operator must stage `metric_depth_vit_large_800k.pth` (1,647,972,663 B,
sha256 15328ffc…) byte-exact in `controlnet`, as
`huggingface/JUGGHM/Metric3D/80d2d1410afb4b23cd9d18c6be9144483d4b70b6/metric_depth_vit_large_800k.pth`. Declaring it as an
`on_demand` weight would need its own code and manifest change (review B-L1).
vit-large needs a guest memory budget of about 6.5 GB. The sealed payload, the decoded state and the model coexist (this
run's cgroup peak was 6.44 GB at 8 GiB, sandbox off). A checkpoint at the 2 GiB ceiling would need about 7 GB (review
B-L2).

Counts: unchanged (52 tested (scoped), 3 converted but untested/partly tested, 9 partial or missing).

## Revision 7 (2026-10-21): DiffusionEdge urban and natrual

Revision 7 tests DiffusionEdge's other two environments. Until now only indoor was inspected and tested, so urban and
natrual refused even after approval (a revision 6 residual). There are no code changes: the run used the revision 6 bytes.

| Environment | Main checkpoint (hr16/Diffusion-Edge @ 401c6cd4) | Bytes | sha256 | Format and globals | Total with the auxiliaries (budget 2 GiB) |
| --- | --- | --- | --- | --- | --- |
| indoor (revision 5) | `diffusion_edge_indoor.pt` | 1,192,128,970 | 3e6e5a0d… | zip, 4 default-allowlisted | 2,097,224,347 B |
| urban | `diffusion_edge_urban.pt` | 1,192,128,970 | 9b0dc9df… | zip, the same 4 | 2,097,224,347 B |
| natrual | `diffusion_edge_natrual.pt` | 1,192,112,522 | ad544682… | zip, the same 4 | 2,097,207,899 B |

Evidence (`validation/20261021-controlnet-aux-diffusionedge-envs-a2base-r1/`):
one selected bounded attempt on the a2 base (core a2 `d1a9259`, backend a1 `894ead3`) and the revision 6 bytes, sandbox
off, CPU, one thread, 8 GiB; peak 5.33 GB, 176 s.
- Inspection, for each main checkpoint:
  - the pins, the archive format and the globals, read through the pack's own helper;
  - three identical decodes: restricted BytesIO, the same after ComfyUI's safe globals, and the original's torch.load.
  A test-only approved selection was derived from these facts: the indoor one, plus each environment's main. The pack's
  own validator accepted it, and the evidence holds it byte-exact, with its hash.
- Parity, for each environment:
  - the pack as published refuses with its own text;
  - the genuine original, an ordinary guest and the registered node in process are exactly equal. The input is the one
    revision 5 used: the 64x64 fixture at resolution 320, patch_batch_size 4;
  - exactly 4 sealed reads, and the buffers are released;
  - the guest without `assets` is refused.
MERVYN fetched the two checkpoints from the pinned revision, one attempt each, with size and sha256 from Hugging Face's
tree metadata. They are test inputs and are never committed.

The independent review of the revision 6 code was CLEAR_WITH_NOTES, with no high or medium findings. This revision folds in
its two Lows on report text: the revision 6 residuals now state which record each zip parser reads, and list that fix as
due before any #21 approval.

Live: unchanged. Each environment used on live needs its own main checkpoint (about 1.19 GB) staged by the operator,
byte-exact, with the three shared auxiliaries. It also needs a production selection that carries that environment's
facts (request #21).

Counts: unchanged (52 tested (scoped), 3 converted but untested/partly tested, 9 partial or missing).

## Revision 6 (2026-10-21): review follow-ups (restricted-decode hardening)

Revision 6 fixes, in code, the follow-ups of the revision 4 and 5 reviews, and re-tests the three affected families
exactly on the new bytes. It changes no count and no live gate.

Changes (production code; independent production review before publication):
- `_restricted_globals.py` (the shared zip proof; UniFormer, Metric3D, and DiffusionEdge main and swin_b):
  - L1: the payload must start with the zip local-file header, the only bytes for which torch takes the zip route. A
    legacy pickle stream with a zip appended would pass the old zip proof, while torch decodes the unscanned legacy pickles
    (review Low-1).
  - L2: `data.pkl` must be STORED, as torch.save writes it, and at most 64 MiB.
  - L3: any open, read or scan error is one clean refusal.
- `_restricted_legacy_globals.py`: only the first 64 MiB is scanned, so the bound also holds inside one pickle (Low-2).
- `_uniformer/selection.py`, `_metric3d/selection.py`:
  - M1: the per-checkpoint `pickle_globals` pin is checked when the selection is validated, before any vendor import,
    config evaluation or read.
  - L4: the selection pins `torch_runtime_version`. The running build is compared before the sealed read (Low-3) and
    again at decode.
- `_diffusionedge/selection.py`:
  - Low-1: before the dispatch, the pinned `archive_format` must match the archive's first four bytes.
  - Low-3: the torch build is compared before the 2.1 GB read and the model build, and again at each decode.
  - Low-4: the sealed buffers are cleared when the construction ends, including after a refusal.
  - The duplicate `import torch` and `record=` lines are gone.
- `tests/test_uniformer_native_registered.py`, `tests/test_metric3d_native_registered.py` (NOT_RUN gates; L5): they now
  assert the pinned torch build, the pinned default-allowlisted globals and the shipped `{raw, assets, models.download}`.
  Out of scope: the Metric3D gate still plans vit-large and vit-giant2, which exceed the 512 MiB read limit.
- The selection files stay `approved: false` (request #21). An approved UniFormer or Metric3D selection now also needs
  `torch_runtime_version`.

Evidence (`validation/20261021-controlnet-aux-followups-a2base-r1/`):
one selected bounded attempt on the a2 base (core a2 `d1a9259`, backend a1 `894ead3`), sandbox off, CPU, one thread,
8 GiB. Three phases ran in separate interpreters; peak 6.07 GB, 268 s.
- A (UniFormer, SemSeg, Metric3D Depth and Normal):
  - The pack as published refuses with its own text.
  - The genuine original, an ordinary guest and the registered node in process are exactly equal (revision 4 inputs).
  - Fail-closed rows refused exactly, with no sealed read: a missing `pickle_globals` and a missing torch pin (both
    before the vendor import), and a wrong torch pin.
- P (DiffusionEdge):
  - The revision 5 parity rows again: original, guest and in process exactly equal. Exactly 4 sealed reads, and the
    buffers are empty after the construction.
  - Nine fail-closed rows refused exactly, with the expected read counts and the buffers emptied after each decode
    refusal. They cover both format directions, a wrong or missing torch pin, an unknown format, wrong and extra globals,
    and a host-registered global (`numpy.dtype`) pinned exactly.
- U: 14 helper rows:
  - the six real archives are accepted;
  - a polyglot (accepted by the old zip proof) is refused;
  - DEFLATED, oversized and truncated `data.pkl` records are refused;
  - a legacy pickle over the 64 MiB cap is refused;
  - host-registered globals are refused in both formats;
  - a zip given to the legacy proof is refused.

Review follow-ups:
- Done: M1 and L1–L5 (the revision 4 review), and Low-1 to Low-5 (the revision 5 review).
- Residuals:
  - L1 ties the route to torch's own test. L2 bounds the scanned record. Which record torch reads (miniz: the first
    entry's prefix, a case-insensitive lookup, the declared central directory) can still differ from the record
    zipfile selects (review A-L1). This is mitigated by sha256 pinning and by the inspection's decode without host
    globals.
    (Revision 9: closed - the proof now scans only the record torch's own reader returns; see "Revision 9".)
  - Fix before any #21 approval (review A-L1): the zip proof must scan the record torch decodes. Python's zipfile
    and torch's miniz differ in at least four ways: the case-insensitive lookup under the first entry's directory,
    the central-directory discovery, NUL-truncated names, and the Info-ZIP Unicode path extra field. The planned
    fix compares the scanned bytes with torch's own `PyTorchFileReader.get_record('data.pkl')`, with unit rows.
    (Closed in revision 9: the fix is in and tested; see "Revision 9".)
  - Known gap (revision 9 review N2): the second read is torch's own `PyTorchFileReader.get_record`, which is not
    separately bounded. If the two readers disagree, torch allocates its record's author-declared size before the
    comparison refuses (a zip-bomb shape): a clean refusal or an OOM kill, never a mis-scan. Not a regression (torch.load
    reads the same record and main's helper would accept the file), and sha256-pinned files cannot reach it.
  - Before #21 (revision 9 review N1): assert in the spy that the reader is exactly `torch._C.PyTorchFileReader`, and add
    one mismatched archive built with ordinary `zipfile.writestr` (`archive/version`, then `archive/Data.pkl` and
    `x/data.pkl`) that main accepts and the candidate refuses. Deferred to the next code round (ordinary zipfile usage).
    (Closed in revision 10: tested — the pre-fix helper accepts it and revision 9 refuses it; see "Revision 10".)
  - Low-4 covers the buffers dict. Two other cases stay referenced until the exception is dropped (bounded by the 2 GiB
    budget): the bytes of a refused archive, and resources already read when a later read fails.
  - Any torch upgrade turns the three families off until they are re-inspected (by design: the pins name the build).
  - DiffusionEdge's urban and natrual main checkpoints are not inspected. Whether they fit the 2 GiB budget is unknown.
    (Closed in revision 7: both are inspected and tested, and both fit.)
  - The Metric3D NOT_RUN gate still plans vit-large and vit-giant2 (out of scope, see above).
    (Revision 8: vit-large now fits the budget and is tested; vit-giant2 still refuses.)

Live: unchanged (requests #21, #23, #24 and #25, and operator staging of the undeclarable weights).

Counts: unchanged (52 tested (scoped), 3 converted but untested/partly tested, 9 partial or missing).

## Revision 5 (2026-10-21): DiffusionEdge (yacs)

Revision 5 ports and tests DiffusionEdge_Preprocessor (environment indoor). It needed three things:
- chunked sealed reads of its four archives (the main checkpoint is 1.19 GB);
- a restricted-globals proof that also covers legacy (non-zip) torch archives;
- a test-env `yacs`.

Changes (production code; independently reviewed: CLEAR_WITH_NOTES, no high or medium findings):
- `_diffusionedge/denoising_diffusion_pytorch/data.py`: the module-level `import albumentations` is removed. The file
  never references it, and its only users are training datasets (`imagenet.py`, `taming/data/*`) outside the inference
  closure, so albumentations stays out of the live profile. `_diffusionedge/source-closure.json` follows (data.py's record).
- `_diffusionedge/selection.py`:
  - Reads: the four sealed archives are read through `_sealed_asset_read` (bounded `read_range`, size and sha256
    verified) instead of `assets.read_bytes` (64 MiB guest cap). The 64 MiB and per-archive 1 GiB refusals are gone;
    the 2 GiB total stays. Each archive's sealed bytes are released at its single decode.
  - Pins: the selection pins `torch_runtime_version`, and per archive `archive_format` (zip or legacy) and
    `pickle_globals`. All must be present before any vendor import or asset read. The torch build itself is compared at
    decode (follow-up Low-3 below).
  - Decode: each restricted decode first refuses another torch build. It then proves the archive uses only its pinned,
    default-allowlisted globals: zip archives through `_restricted_globals.py` (unchanged), legacy archives through
    `_restricted_legacy_globals.py` (new).
- `_restricted_legacy_globals.py` (new, shared):
  - A BytesIO legacy load never takes torch's tar route, so it loads exactly five pickles with the weights_only
    unpickler. Their globals are scanned with torch's own scanner, and must equal the pin and be default-allowlisted.
  - Fail-closed: zip payloads are refused, and any error is one refusal. The scanned bytes are capped at 64 MiB, but
    the cap is checked after each pickle (follow-up Low-2 below).
- `secure-nodes.json`: DiffusionEdge_Preprocessor gains `assets` and declares no required weights:
  - vgg16 and swin_b (torchvision URLs) and LPIPS `vgg.pth` (a file in the pack's source tree) have no declarable
    source (SDK gap);
  - the main checkpoint, a Hugging Face file, is deliberately not declared. Declaring it would add `models.download`
    and a 1.19 GB download before the selection refusal (the #23 pattern), and a partial declaration would not make the
    node runnable.
- The selection file stays `approved: false` (request #21).

Evidence (`validation/20261021-controlnet-aux-diffusionedge-a2base-r1/`):
two selected bounded runs on the a2 base (core a2 `d1a9259`, backend a1 `894ead3`), sandbox off, CPU, one thread, 8 GiB.
- Tier I (inspection):
  - main and swin_b are zip archives; vgg16 and LPIPS `vgg.pth` are legacy pickles;
  - every global is in torch's default allowlist;
  - each decode is identical with ComfyUI's safe globals registered and through the original's own `torch.load`;
  - peak 2.9 GB.
- Tier P (parity) ran under a test-only approved selection built from Tier I (hashes recorded) and a test-env `yacs` 0.1.8:
  - The pack as it would ship refuses with its own "selection pending" text.
  - The genuine pristine original, an ordinary guest and the registered node in process gave exactly equal outputs: a
    64x64 fixture at resolution 320 (one 320x320 window), patch_batch_size 4. The guest ran with the sandbox off, as in
    revision 4. The original side ran offline with a test-only empty `albumentations`, which upstream imports unused.
    The converted side had albumentations blocked.
  - The guest without `assets` was refused.
  - Fail-closed rows, run in process, refused exactly:
    - a missing global pin;
    - a legacy archive pinned as zip;
    - a wrong global list;
    - a legacy copy with one extra unpinned global, built in the harness;
    - a wrong torch pin.
  - Peak memory was 6.03 GB in the fail-closed rows and 5.05 GB in the parity rows. The run took 126 s.

Live: DiffusionEdge refuses "selection pending" until its selection is approved (request #21). Then it needs:
- `yacs` 0.1.8 in the live Aux profile (request #25);
- operator staging of all four weight files (about 2.1 GB, byte-exact sha256) in `controlnet`, under the production
  selection's catalogue names: the torchvision and LPIPS files have no declarable source, and the main checkpoint is
  deliberately not declared (see `secure-nodes.json` above);
- a production selection that pins the live torch build string exactly, with each archive's `archive_format` and
  `pickle_globals` from an inspection on that build. Any later torch upgrade turns the node off until it is re-inspected;
- a guest memory budget of at least about 6 GB.
It declares no required weights, so request #23 does not apply.

Review follow-ups. The independent review of port r2 was CLEAR_WITH_NOTES (no high or medium findings). This updates
the revision 4 list:
- M1 and L4 are done for DiffusionEdge. Its selection pins `pickle_globals`, `archive_format` and
  `torch_runtime_version` before any vendor import or read, and its decode refuses another torch build.
- Open, to fix before any #21 approval:
  - L1–L3 on the shared zip helper `_restricted_globals.py`, which DiffusionEdge's main and swin_b now also use
    (review Low-1). A crafted polyglot, a legacy pickle stream with a zip appended, would pass the zip proof while
    torch decodes the legacy pickles, which were never scanned. The pinned bytes cannot do this: they are sha-pinned,
    and their leading bytes were verified.
  - Low-2: the legacy helper checks its 64 MiB scan bound only after each pickle has been scanned.
  - Low-3: the torch pin is compared at decode, after the 2.1 GB read and the model build. It still fails closed
    before any decode.
  - Low-4: on a refusal, or for a resource that is never decoded, the sealed bytes stay referenced until the exception
    is dropped. The fix clears the buffers when construction ends.
  - Low-5, test gaps: there is no row for a zip archive pinned as legacy, for a host-registered global pinned exactly,
    or for a missing `torch_runtime_version` or an unknown `archive_format`.
  - M1, L4 and L5 for UniFormer and Metric3D (the revision 4 list).
- These become one small code revision with a combined re-run (UniFormer and Metric3D Tier A, DiffusionEdge Tier P)
  before request #21.

Counts: tested (scoped) 51 → 52; open 10 → 9 (6 pending capability: the six transformers-bundle nodes; 3 blocked by the
platform).

## Revision 4 (2026-10-21): UniFormer, SemSeg and Metric3D (addict)

Revision 4 ports and tests four pending-capability nodes: UniFormer-SemSegPreprocessor, SemSegPreprocessor (its alias),
Metric3D-DepthMapPreprocessor and Metric3D-NormalMapPreprocessor. Their only missing dependency was `addict`, which the
vendored mmcv Config imports at module level.

Changes (production code; independent review CLEAR_WITH_NOTES, follow-ups listed below):
- `_uniformer/selection.py` and `_metric3d/selection.py`:
  - The whole sealed checkpoint is read through `_sealed_asset_read` (bounded `assets.read_range`, size and sha256
    verified), because the guest caps `assets.read_bytes` at 64 MiB.
  - The blanket "no safe globals registered" refusal could never hold under ComfyUI. It is replaced by a per-checkpoint
    proof that the restricted decode uses only torch's default-allowlisted globals (`_restricted_globals.py`, new).
- `secure-nodes.json`: the four rows gain `assets` and `models.download`, and one declared weight each:
  `upernet_global_small.pth` from lllyasviel/Annotators, and `metric_depth_vit_small_800k.pth` from JUGGHM/Metric3D
  (the upstream default backbone).
- The selection files stay `approved: false` (request #21).

Evidence (`validation/20261021-controlnet-aux-addict4-a2base-r1/`):
one selected bounded run on the a2 base (core a2 `d1a9259`, backend a1 `894ead3`), sandbox off, CPU, one thread, 4 GiB.
- Control rows: the pack as it would ship refuses all four nodes with its own "selection pending" text. On live today,
  dispatch refuses them before that (request #23).
- The parity rows ran under a test-only approved selection supplied by the harness (hashes recorded) and with a test-env
  `addict` 2.4.0:
  - The genuine pristine original, an ordinary guest and the registered node in process gave exactly equal outputs
    (checker 64x64, resolution 64; Metric3D with vit-small and fx = fy = 1000).
  - The guest without `assets` was refused.
  - Metric3D depth differs from normal, and the original's checkpoint path matched the selection.
  - Peak memory was 3.39 GB, and the run took 180 s.

Limitation: Metric3D is tested with vit-small only. vit-large (1.65 GB) and vit-giant2 (5.51 GB) exceed the selection
code's 512 MiB read limit, so they refuse even after approval, although the backbone dropdown offers them.

Live (request #23, new): every node that declares required weights is refused at dispatch. Live never grants
`models.download`, and the required-weights check runs before any installed file is reused.
- This affects 24 of the 51 tested Aux nodes: the 20 rows marked "Live:" plus the four above.
- With #23 fixed, six of revision 3's eight #21 nodes declare weights and still raise a selection error until #21.
  AnimalPose and DensePose declare no weights, so #21 is their first refusal.
- The revision 4 nodes also need `addict` 2.4.0 in the live Aux profile (request #24).

Counts: tested (scoped) 47 → 51; open 14 → 10 (7 pending capability: DiffusionEdge and the six transformers-bundle nodes;
3 blocked by the platform).

Review follow-ups (fix before any #21 approval). The independent review of the port found no blockers
(CLEAR_WITH_NOTES). These items become their own small code revision, with a Tier A re-run, before request #21:
- M1: `resource.pickle_globals` is a new required selection field: approved selections must carry it, sorted and exact,
  taken from the restricted inspection. It is checked only at decode, after the vendor imports and the config
  evaluation, which breaks "selection before imports". It fails closed. The fix changes selection.py, so Tier A re-runs.
- L1: a zip leading-bytes check in `_restricted_globals.py`.
- L2: a size bound on the `data.pkl` read.
- L3: more error types wrapped into clean refusals.
- L4: keep torch pinned (the helper uses private torch helpers).
- L5: the shipped tests `tests/test_uniformer_native_registered.py:71,75` and
  `tests/test_metric3d_native_registered.py:69,71` still assert no safe globals and `{raw, assets}`, so they are
  stale for this port.
- With consent granted, live would first download the 206 MB or 150 MB weight and only then refuse "selection pending".
  That is another reason why request #23 option (a), staged pinned weights, is the right fix.

## Revision 3 (2026-10-21, docs only): live selection status

Only this report changes. No code, manifest, selection file or test changed, and nothing was run.

**Eight nodes counted as tested refuse on the live service.** Their scoped tests ran with model selections that were
approved for the test only. Revision 2 published the selection files without those approvals ("production admission stays
closed"). So on live each of these nodes raises a "… selection pending" or "… unselected" error before it loads anything:

| Node | Gate (selection file) |
| --- | --- |
| DepthAnythingV2Preprocessor | `_depth_v2_selection.py` (`_depth_v2_asset_selection.json`) |
| DWPreprocessor, AnimalPosePreprocessor | `_dwpose/selection.py` (`_dwpose/asset-selection.json`) |
| DensePosePreprocessor | `_densepose/selection.py` (`_densepose/asset-selection.json`) |
| LeReS-DepthMapPreprocessor | `_leres/selection.py` (`_leres/asset-selection.json`) |
| MiDaS-DepthMapPreprocessor, MiDaS-NormalMapPreprocessor | `_midas/managed_components.py` (`_midas/SELECTION.json`) |
| Unimatch_OptFlowPreprocessor | `_unimatch/selection.py` (`_unimatch/asset-selection.json`) |

AIO_Preprocessor fails the same way when one of these is selected. Two families need more than an approval:
- MiDaS's code accepts only a test-only selection, so it also needs a code change for production.
- DensePose, DWPose and AnimalPose also need weights that `required_weights` cannot declare (TorchScript archives) to be
  present in the live store.

Four pending-capability nodes are blocked the same way once `addict` is available: UniFormer-SemSegPreprocessor,
SemSegPreprocessor, Metric3D-DepthMapPreprocessor and Metric3D-NormalMapPreprocessor. These 12 nodes wait on request #21,
which asks who may approve a model selection for production, and with what evidence. The other open nodes' selections are
unapproved too, but they have earlier blockers (requests #16-#20).

Not affected, provided their declared weights are in the live store:
- the families whose published selections are approved (DSINE, BAE, OpenPose);
- the families with no selection file (HED, PiDiNet, M-LSD, line art, manga, TEED, AnyLine) and the non-model nodes.

So at most 39 of the 47 tested nodes can run on live today.

The open nodes now carry request numbers:
- #16: a sealed transformers bundle constructor (6 nodes);
- #17: FaceMesh on Python 3.13;
- #18: MeshGraphormer (EGL/GLES libraries in the engine image, then dependencies and weights);
- #19: the two guest-route SDK gaps (AnimeFace output typing, UpperBodyTracking plain-data types);
- #20: ExecuteAll.

Correction: ExecuteAll's execute raises today. The original's 140-node expansion exceeds the SDK's 128-node limit and uses
core ImageBatch, which converted packs cannot target.

Counts are unchanged. The scoped evidence stands, and the rows of the eight nodes now say they refuse on live.

Evidence: `validation/20261021-controlnet-aux-live-selection-status/`.
It lists each gate with its line and file hash, and the approval flags of each selection file at this revision.

## Per-node status (2026-10-15, revision 2)

Dispositions: **tested** = scoped behavior evidence on the registered node (revision-2 additions: in-process registered node AND ordinary guest, each bit-exact vs the genuine upstream original on the same staged weights, CPU, capped container); **partial** = source converted, positive behavior only partly tested; **pending-capability** = source converted but blocked on a capability (dependency, constructor, memory); **blocked (platform)** = source converted but the runtime platform cannot host the original dependency.

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| AIO_Preprocessor | AIO Aux Preprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `aio-shared-and-full-cli-original-dispatch-pass-r2`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| AnimalPosePreprocessor | AnimalPose Estimator (AP10K) | tested | TorchScript pair; in-process and guest exact vs the genuine original, cold and warm — evidence: `tests/dwpose-animalpose-inprocess-and-guest-vs-original-r1`. **Refuses on live today: its published model selection is unapproved, so it raises a selection error before loading anything (request #21; revision 3).** It also needs undeclarable TorchScript weights in the live store. |
| AnimeFace_SemSegPreprocessor | Anime Face Segmentor | partial | In-process exact vs the genuine original (both background modes). Guest blocked by an SDK gap: guest outputs are typed by value, so upstream's 4-D NCHW MASK is validated as IMAGE and refused. Evidence: `tests/animeface-inprocess-exact-guest-blocked-sdk-output-typing-r1`. Guest route: request #19. |
| AnimeLineArtPreprocessor | Anime Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anime-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| AnyLineArtPreprocessor_aux | AnyLine Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anyline-shared-and-full-cli-original-model-pass-r2`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| BAE-NormalMapPreprocessor | BAE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `bae-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| BinaryPreprocessor | Binary Lines | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| CannyEdgePreprocessor | Canny Edge | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ColorPreprocessor | Color Pallete | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ControlNetAuxSimpleAddText | ControlNetAuxSimpleAddText | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| ControlNetPreprocessorSelector | Preprocessor Selector | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| DensePosePreprocessor | DensePose Estimator | tested | r50, both cmaps, person image; in-process and guest exact vs the genuine original. Declared assets-only: a `.torchscript` archive cannot be a required weight (SDK). Evidence: `tests/densepose-r50-inprocess-and-guest-vs-original-r1`. **Refuses on live today: its published model selection is unapproved, so it raises a selection error before loading anything (request #21; revision 3).** It also needs its undeclarable TorchScript archive in the live store. |
| DepthAnythingPreprocessor | Depth Anything | pending-capability | Upstream maps the `.pth` labels to LiheYoung/depth-anything-*-hf bundles; needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Request #16. |
| DepthAnythingV2Preprocessor | Depth Anything V2 - Relative | tested | vits checkpoint; in-process and ordinary guest exact vs the genuine original — evidence: `tests/depthv2-vits-inprocess-and-guest-vs-original-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** |
| DiffusionEdge_Preprocessor | Diffusion Edge (batch size ↑ => speed ↑, VRAM ↑) | tested | tested (scoped): test-only approved selection and a test-env yacs 0.1.8 (harness; hashes recorded). Live: refuses 'selection pending' until the selection is approved (#21); then needs yacs in the Aux profile (#25) and operator staging of all four weight files (about 2.1 GB, byte-exact): the torchvision and LPIPS files have no declarable source, and the main checkpoint is deliberately not declared (declaring it would add models.download and a 1.19 GB download before the selection refusal). Evidence: `validation/20261021-controlnet-aux-diffusionedge-a2base-r1/` (revision 5: in process and ordinary guest exactly equal to the genuine original; the 64x64 fixture at resolution 320, one 320x320 window, patch_batch_size 4, indoor; fail-closed rows for the per-archive globals proof and the torch pin). Revision 6: re-tested exactly on the hardened restricted decode (`validation/20261021-controlnet-aux-followups-a2base-r1/`). Revision 7: urban and natrual also tested exactly (`validation/20261021-controlnet-aux-diffusionedge-envs-a2base-r1/`). |
| DSINE-NormalMapPreprocessor | DSINE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `dsine-shared-full-cli-original-member-model-pass-r4`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| DWPreprocessor | DWPose Estimator | tested | yolox_l.onnx (OpenCV DNN, as upstream routes it here) + dw-ll TorchScript; in-process and guest exact vs the genuine original, cold and warm — evidence: `tests/dwpose-animalpose-inprocess-and-guest-vs-original-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** It also needs undeclarable TorchScript weights in the live store. |
| ExecuteAllControlNetPreprocessors | Execute All ControlNet Preprocessors | partial | Schema discovery passes (canonical successor). A full positive run needs a graph executor with every child preprocessor runnable; blocked children are listed in this table. Correction (revision 3): its execute raises today, because the original 140-node expansion exceeds the SDK's 128-node limit and uses core ImageBatch (request #20). |
| FacialPartColoringFromPoseKps | Colorize Facial Parts from PoseKPS | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| FakeScribblePreprocessor | Fake Scribble Lines (aka scribble_hed) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| HEDPreprocessor | HED Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| HintImageEnchance | Enchance And Resize Hint Images | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromImage | Generation Resolution From Image | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromLatent | Generation Resolution From Latent | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageIntensityDetector | Image Intensity | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageLuminanceDetector | Image Luminance | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| InpaintPreprocessor | Inpaint Preprocessor | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| LeReS-DepthMapPreprocessor | LeReS Depth Map (enable boost for leres++) | tested | Default and boost; in-process and guest exact vs the genuine original — evidence: `tests/leres-inprocess-and-guest-vs-original-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** |
| LineArtPreprocessor | Realistic Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `lineart-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| LineartStandardPreprocessor | Standard Lineart | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| M-LSDPreprocessor | M-LSD Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `mlsd-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| Manga2Anime_LineArt_Preprocessor | Manga Lineart (aka lineart_anime_denoise) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `manga-shared-and-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| MaskOptFlow | Mask Optical Flow (DragNUWA) | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| MediaPipe-FaceMeshPreprocessor | MediaPipe Face Mesh | blocked (platform) | blocked: needs the legacy mediapipe `mp.solutions` API, absent from every mediapipe wheel for Python 3.13 (checked 1.1.1, 0.10.35, 0.10.31). Evidence: `tests/facemesh-mediapipe-legacy-solutions-absent-py313-r1`. Reopens if a <=3.12 side runtime exists. Request #17. |
| MeshGraphormer+ImpactDetector-DepthMapPreprocessor | MeshGraphormer Hand Refiner With External Detector | blocked (platform) | As MeshGraphormer-DepthMapPreprocessor, plus an Impact-Pack detector (external pack). Request #18. |
| MeshGraphormer-DepthMapPreprocessor | MeshGraphormer Hand Refiner | blocked (platform) | blocked: mediapipe's native `libmediapipe.so` needs `libEGL.so.1` + `libGLESv2.so.2`, absent from the engine image, so the Tasks HandLandmarker cannot load. Evidence: `tests/meshgraphormer-mediapipe-profile-proof-r1`. Then: mediapipe==0.10.35 profile request (queued), trimesh, yacs, weights, MANO/SMPL data. Request #18. |
| Metric3D-DepthMapPreprocessor | Metric3D Depth Map | tested | tested (scoped): test-only approved selection and a test-env addict 2.4.0 (harness; hashes recorded). Live: dispatch refuses first (#23, required_weights); with #23 fixed it refuses 'selection pending' until #21; addict is not in the live Aux profile (#24). Evidence: `validation/20261021-controlnet-aux-addict4-a2base-r1/` (revision 4: in process and ordinary guest exactly equal to the genuine original; checker 64x64, resolution 64, vit-small, fx = fy = 1000). Tested with vit-small (revision 4) and vit-large (revision 8: `validation/20261021-controlnet-aux-metric3d-large-a2base-r1/`). vit-giant2 (5.51 GB) exceeds the 2 GiB per-checkpoint budget and refuses at selection time, before any read, although the dropdown offers it (tested in revision 8). Revision 6: re-tested exactly on the hardened restricted decode (`validation/20261021-controlnet-aux-followups-a2base-r1/`). |
| Metric3D-NormalMapPreprocessor | Metric3D Normal Map | tested | tested (scoped): test-only approved selection and a test-env addict 2.4.0 (harness; hashes recorded). Live: dispatch refuses first (#23, required_weights); with #23 fixed it refuses 'selection pending' until #21; addict is not in the live Aux profile (#24). Evidence: `validation/20261021-controlnet-aux-addict4-a2base-r1/` (revision 4: in process and ordinary guest exactly equal to the genuine original; checker 64x64, resolution 64, vit-small, fx = fy = 1000). Tested with vit-small (revision 4) and vit-large (revision 8: `validation/20261021-controlnet-aux-metric3d-large-a2base-r1/`). vit-giant2 (5.51 GB) exceeds the 2 GiB per-checkpoint budget and refuses at selection time, before any read, although the dropdown offers it (tested in revision 8). Revision 6: re-tested exactly on the hardened restricted decode (`validation/20261021-controlnet-aux-followups-a2base-r1/`). |
| MiDaS-DepthMapPreprocessor | MiDaS Depth Map | tested | In-process and ordinary guest exact vs the native golden (scoped, isolated) — evidence: `tests/midas-learned-inprocess-and-guest-isolated-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** Its code also accepts only a test-only selection. |
| MiDaS-NormalMapPreprocessor | MiDaS Normal Map | tested | In-process and ordinary guest exact vs the genuine original — evidence: `tests/midas-normal-inprocess-and-guest-vs-original-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** Its code also accepts only a test-only selection. |
| OneFormer-ADE20K-SemSegPreprocessor | OneFormer ADE20K Segmentor | pending-capability | shi-labs/oneformer_ade20k_swin_large bundle + the class-info JSON transformers fetches from the shi-labs/oneformer_demo dataset repo; needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Request #16. |
| OneFormer-COCO-SemSegPreprocessor | OneFormer COCO Segmentor | pending-capability | shi-labs/oneformer_coco_swin_large bundle + class-info JSON (shi-labs/oneformer_demo); needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Request #16. |
| OpenposePreprocessor | OpenPose Pose | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `openpose-original7-HTTP-full1591-CLI-scoped-pass-r5`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| PiDiNetPreprocessor | PiDiNet Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| PixelPerfectResolution | Pixel Perfect Resolution | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| PyraCannyPreprocessor | PyraCanny | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| RenderAnimalKps | Render Pose JSON (Animal) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| RenderPeopleKps | Render Pose JSON (Human) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| SAMPreprocessor | SAM Segmentor | pending-capability | Upstream default at this pin is `facebook/sam-vit-base` via transformers (`mobile_sam.pt` is only a label; vendored MobileSAM code is unreachable); needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Upstream uses the global numpy RNG (nondeterministic). Request #16. |
| SavePoseKpsAsJsonFile | Save Pose Keypoints | tested | Scoped original managed-output pass on shared HTTP and full-source CLI — evidence: `savepose-shared-full-cli-original-json-scoped-pass-r4` |
| Scribble_PiDiNet_Preprocessor | Scribble PiDiNet Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| Scribble_XDoG_Preprocessor | Scribble XDoG Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ScribblePreprocessor | Scribble Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| SemSegPreprocessor | Semantic Segmentor (legacy, alias for UniFormer) | tested | tested (scoped): test-only approved selection and a test-env addict 2.4.0 (harness; hashes recorded). Live: dispatch refuses first (#23, required_weights); with #23 fixed it refuses 'selection pending' until #21; addict is not in the live Aux profile (#24). Evidence: `validation/20261021-controlnet-aux-addict4-a2base-r1/` (revision 4: in process and ordinary guest exactly equal to the genuine original; checker 64x64, resolution 64). Revision 6: re-tested exactly on the hardened restricted decode (`validation/20261021-controlnet-aux-followups-a2base-r1/`). |
| ShufflePreprocessor | Content Shuffle | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TEEDPreprocessor | TEEDPreprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `teed-shared-and-full-cli-same-runtime-original-model-pass-r2`. Live: refused at dispatch (request #23: it declares required weights, and live never grants `models.download`). |
| TilePreprocessor | Tile | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileGF_Preprocessor | TTPlanet Tile GuidedFilter | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileSimple_Preprocessor | TTPlanet Tile Simple | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| UniFormer-SemSegPreprocessor | UniFormer Segmentor | tested | tested (scoped): test-only approved selection and a test-env addict 2.4.0 (harness; hashes recorded). Live: dispatch refuses first (#23, required_weights); with #23 fixed it refuses 'selection pending' until #21; addict is not in the live Aux profile (#24). Evidence: `validation/20261021-controlnet-aux-addict4-a2base-r1/` (revision 4: in process and ordinary guest exactly equal to the genuine original; checker 64x64, resolution 64). Revision 6: re-tested exactly on the hardened restricted decode (`validation/20261021-controlnet-aux-followups-a2base-r1/`). |
| Unimatch_OptFlowPreprocessor | Unimatch Optical Flow | tested | scale2-regrefine6; in-process and guest exact vs the genuine original; checkpoint `_metadata` accepted only via the recorded per-checkpoint equivalence proof — evidence: `tests/unimatch-scale2-regrefine6-inprocess-and-guest-vs-original-r1`. **Live: refused at dispatch first (request #23: it declares required weights); with #23 fixed it raises a selection error until request #21 (revisions 3 and 4).** |
| UpperBodyTrackingFromPoseKps | Upper Body Tracking From PoseKps (InstanceDiffusion) | partial | Populated multi-person / multi-frame cases: in-process exact vs the genuine original. Guest wire changes plain-data types (int dict keys -> str, numpy float64 -> Tensor); prompt string exact. Evidence: `tests/upperbody-tracking-inprocess-exact-guest-wire-typing-r1`. Guest route: request #19. |
| Zoe-DepthMapPreprocessor | Zoe Depth Map | pending-capability | Intel/zoedepth-nyu-kitti bundle; needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Request #16. |
| Zoe_DepthAnythingPreprocessor | Zoe Depth Anything | pending-capability | Upstream uses Intel/zoedepth-nyu-kitti for both metric defaults; needs a sealed transformers bundle constructor (GERALD; exact needs in the Aux group-2 constructor-needs document) plus the bundle files. Request #16. |

## Revision 2 changes

### Pack-local source fixes (shipped)

| File | Why |
| --- | --- |
| `_densepose/selection.py` | sealed whole-archive read via `_sealed_asset_read.py` |
| `_dwpose/__init__.py` | per-invocation construction: the native module caches are emptied before and after each call (warm == cold proven exact), so no model outlives its invocation |
| `_dwpose/selection.py` | per-invocation sealed-content binding (no realm identity, no cross-invocation cache) replaces the unconditional hold; ONNX via OpenCV DNN byte constructor only while upstream's own routing selects cv2 (pinned OpenCV); sealed read |
| `_leres/detector.py` | nested `res101.pth` read via `assets.load_state_dict(ref, member="depth_model")` (the DSINE precedent); the guest weight bridge refuses the whole nested container |
| `_restricted_globals.py` | shared (revision 4): the restricted torch decode proof for zip archives — the checkpoint's single `data.pkl` may reference only its pinned, default-allowlisted globals (UniFormer, Metric3D, DiffusionEdge); revision 6: L1-L3 (leading bytes, a STORED and bounded data.pkl, one clean refusal); revision 9: scans only when the bounded record equals torch's own `PyTorchFileReader.get_record('data.pkl')`, so the two zip readers cannot disagree (review A-L1) |
| `_restricted_legacy_globals.py` | shared (revision 5): the same proof for legacy (non-zip) archives — the five pickles a BytesIO legacy load reads (DiffusionEdge); revision 6: the 64 MiB bound holds inside each pickle (Low-2) |
| `_sealed_asset_read.py` | shared: whole-archive reads through the bounded `assets.read_range` (<= 16 MiB per call), size + sha256 verified — the guest caps `assets.read_bytes` at 64 MiB |
| `_unimatch/metadata-equivalence-proof.json` | the recorded proof (with/without `_metadata`: identical state and outputs on the original model, this checkpoint only) |
| `_unimatch/selection.py` | checkpoint `_metadata` accepted only with the recorded per-checkpoint equivalence proof (proof sha256 + checkpoint sha256/bytes/revision + torch build); both routes load the metadata-free state |

### Declaration fixes (secure-nodes.json; regenerated by the SDK from this tree)

| Node id | Permissions | Required weights |
| --- | --- | --- |
| DensePosePreprocessor | `raw`, `assets` | — (see note) |
| DepthAnythingV2Preprocessor | `raw`, `assets`, `models.download` | `depth_anything_v2_vits.pth` (depth-anything/Depth-Anything-V2-Small@03876f86, sha256 715fade13be8) |
| AnimalPosePreprocessor | `raw`, `assets`, `models.download` | — (see note) |
| DWPreprocessor | `raw`, `assets`, `models.download` | `yolox_l.onnx` (yzd-v/DWPose@1a714410, sha256 7860ae79de6c) |
| LeReS-DepthMapPreprocessor | `raw`, `assets`, `models.download` | `res101.pth` (lllyasviel/Annotators@982e7eda, sha256 1d696b2ef3e8); `latest_net_G.pth` (lllyasviel/Annotators@982e7eda, sha256 50ec735d74ed) |
| Unimatch_OptFlowPreprocessor | `raw`, `assets`, `models.download` | `gmflow-scale2-regrefine6-mixdata.pth` (hr16/Unimatch@9ef80c9c, sha256 4e7b215d5a25) |
| AnimeFace_SemSegPreprocessor | `raw`, `assets`, `models.download` | `Annotators/UNet.pth` (bdsqlsz/qinglong_controlnet-lllite@67006a35, sha256 96c2a509b3eb); `isnetis.ckpt` (skytnt/anime-seg@493cb608, sha256 2c8f6b9a7738) |

Not declarable today (SDK): executable TorchScript archives (`densepose_r50_fpn_dl.torchscript`, the DW/AnimalPose `*.torchscript.pt` — they fail the restricted-archive check) and download.pytorch.org weights (AnimeFace `mobilenet_v2-b0353104.pth`). These nodes resolve them from the managed store when staged.

### SDK gaps recorded with GERALD (not pack-fixable)

- Guest outputs are typed by value (any non-1-D tensor becomes IMAGE): blocks AnimeFace's native 4-D MASK on the guest route.
- Plain-data guest outputs lose types (int dict keys, numpy scalars): blocks UpperBodyTracking on the guest route.
- `required_weights` cannot declare executable TorchScript or URL-sourced weights.
- Pickled state `_metadata` is dropped by the guest transport (Unimatch carries a per-checkpoint proof instead).

## Refused techniques (never-do) and public replacements

| Refused technique | Public replacement in this conversion |
| --- | --- |
| Importing ComfyUI private core (`comfy.*`, `folder_paths`, model management) inside node code | Public `comfy_api.latest` `io` / `sdk` APIs; private-core references confined to test-only `_test_*` reference helpers |
| Downloading checkpoints at run time (Hugging Face Hub / torch.hub / URLs in `from_pretrained`) | Declared, SHA-256-pinned managed weights resolved by the host; no guest network |
| Unrestricted pickle loading of downloaded checkpoints | Managed loaders / restricted state-dict readers bound to pinned bytes |
| Writing files into the pack folder or arbitrary paths (SavePose JSON) | SDK managed `output` capability |
| Reaching into the executing prompt graph directly (ExecuteAll) | Public graph expansion (`enable_expand`) on the SDK node output |

## Pending (not yet supported — needs <capability>)

- UniFormer-SemSegPreprocessor, SemSegPreprocessor, Metric3D-DepthMapPreprocessor, Metric3D-NormalMapPreprocessor: tested (scoped) in revision 4. On live they need `addict` 2.4.0 in the Aux profile (request #24), production approval of their selections (request #21), and request #23, because they declare required weights.
- DiffusionEdge_Preprocessor: tested (scoped) in revision 5. On live it refuses 'selection pending' until its selection is approved (request #21); then it needs `yacs` in the Aux profile (request #25) and operator staging of all four weight files (about 2.1 GB, byte-exact): the torchvision and LPIPS files have no declarable source, and the main checkpoint is deliberately not declared.
- SAMPreprocessor, DepthAnythingPreprocessor, Zoe_DepthAnythingPreprocessor, Zoe-DepthMapPreprocessor, OneFormer-ADE20K-SemSegPreprocessor, OneFormer-COCO-SemSegPreprocessor: not yet supported — needs a sealed transformers bundle constructor (request #16).
- MediaPipe-FaceMeshPreprocessor: blocked (platform) — needs the legacy mediapipe `mp.solutions` API, absent from every Python 3.13 mediapipe wheel (request #17).
- MeshGraphormer-DepthMapPreprocessor, MeshGraphormer+ImpactDetector-DepthMapPreprocessor: blocked (platform) — needs `libEGL.so.1` + `libGLESv2.so.2` in the engine image, then mediapipe, trimesh, yacs, weights and MANO/SMPL data (request #18).
- AnimeFace_SemSegPreprocessor (guest route): needs SDK output typing by the declared output type (request #19).
- UpperBodyTrackingFromPoseKps (guest route): needs a type-preserving plain-data guest wire (request #19).
- ExecuteAllControlNetPreprocessors: its execute raises today. The original's 140-node expansion exceeds the SDK's 128-node limit and uses core ImageBatch, which converted packs cannot target (request #20). A full positive run also needs every child preprocessor to be runnable.
- Live model selections (request #21): DepthAnythingV2, DWPose, AnimalPose, DensePose, LeReS, MiDaS ×2 and Unimatch (tested, scoped), UniFormer, SemSeg and Metric3D ×2, and DiffusionEdge (revision 5), refuse on live until their selections are approved for production. MiDaS also needs a code change, and DensePose, DWPose and AnimalPose need undeclarable weights in the live store. The nodes among these that declare required weights are refused at dispatch first (request #23). Before any approval, every pinned archive's inspection must include a decode with no host safe globals registered (review A-L2).
- Live dispatch of nodes that declare required weights (request #23): live never grants `models.download`, and the required-weights check runs before any installed file is reused. So 24 tested nodes (20 since revision 2 and the 4 of revision 4) are refused at dispatch.

## Open test gates

- Every pending-capability and blocked node above, once its capability lands.
- AnimeFace and UpperBodyTracking guest routes after the SDK fixes.
- Live: the 13 nodes of request #21 once their selections are approved and the undeclarable weights are in the live store.
- Live: request #23 for the 24 tested nodes that declare required weights, request #24 (`addict`) for the revision 4 nodes, and request #25 (`yacs`) for DiffusionEdge.
- ExecuteAll full run; whole-pack acceptance and normal registry publication: not started.

## Authority / permissions

| Permission set | Nodes |
| --- | --- |
| `raw` | 34 (BinaryPreprocessor, CannyEdgePreprocessor, ColorPreprocessor, ControlNetAuxSimpleAddText, DepthAnythingPreprocessor, ExecuteAllControlNetPreprocessors, …) |
| `raw`, `assets`, `models.download` | 25 (AnimalPosePreprocessor, AnimeFace_SemSegPreprocessor, AnimeLineArtPreprocessor, AnyLineArtPreprocessor_aux, BAE-NormalMapPreprocessor, DSINE-NormalMapPreprocessor, …) |
| `raw`, `assets` | 2 (DensePosePreprocessor, DiffusionEdge_Preprocessor) |
| `assets`, `output` | 1 (SavePoseKpsAsJsonFile) |
| `raw`, `assets`, `models.download`, `output` | 1 (AIO_Preprocessor) |
| (none) | 1 (ControlNetPreprocessorSelector) |

## Assets / weights required (never committed)

Declared managed weights in the regenerated manifest:

| Node id | Declared weights |
| --- | --- |
| AIO_Preprocessor | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013); `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6); `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c); `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725); `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |
| AnimeFace_SemSegPreprocessor | `Annotators/UNet.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 96c2a509b3eb); `isnetis.ckpt` (skytnt/anime-seg, sha256 2c8f6b9a7738) |
| AnimeLineArtPreprocessor | `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf) |
| AnyLineArtPreprocessor_aux | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| BAE-NormalMapPreprocessor | `scannet.pt` (lllyasviel/Annotators, sha256 03dbf1600c51) |
| DSINE-NormalMapPreprocessor | `dsine.pt` (hr16/Diffusion-Edge, sha256 629472c66ea9) |
| DWPreprocessor | `yolox_l.onnx` (yzd-v/DWPose, sha256 7860ae79de6c) |
| DepthAnythingV2Preprocessor | `depth_anything_v2_vits.pth` (depth-anything/Depth-Anything-V2-Small, sha256 715fade13be8) |
| FakeScribblePreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| HEDPreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| LeReS-DepthMapPreprocessor | `res101.pth` (lllyasviel/Annotators, sha256 1d696b2ef3e8); `latest_net_G.pth` (lllyasviel/Annotators, sha256 50ec735d74ed) |
| LineArtPreprocessor | `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061) |
| M-LSDPreprocessor | `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c) |
| Manga2Anime_LineArt_Preprocessor | `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| Metric3D-DepthMapPreprocessor | `metric_depth_vit_small_800k.pth` (JUGGHM/Metric3D, sha256 b34b2a2be914) |
| Metric3D-NormalMapPreprocessor | `metric_depth_vit_small_800k.pth` (JUGGHM/Metric3D, sha256 b34b2a2be914) |
| MiDaS-DepthMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| MiDaS-NormalMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| OpenposePreprocessor | `body_pose_model.pth` (lllyasviel/Annotators, sha256 25a948c16078); `hand_pose_model.pth` (lllyasviel/Annotators, sha256 b76b00d17509); `facenet.pth` (lllyasviel/Annotators, sha256 8beb52e54862) |
| PiDiNetPreprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| Scribble_PiDiNet_Preprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| SemSegPreprocessor | `upernet_global_small.pth` (lllyasviel/Annotators, sha256 bebfa1264c10) |
| TEEDPreprocessor | `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |
| UniFormer-SemSegPreprocessor | `upernet_global_small.pth` (lllyasviel/Annotators, sha256 bebfa1264c10) |
| Unimatch_OptFlowPreprocessor | `gmflow-scale2-regrefine6-mixdata.pth` (hr16/Unimatch, sha256 4e7b215d5a25) |

Upstream-tracked model files excluded from `v2/` (still present in the pristine tree):

| File (upstream path) | Bytes |
| --- | --- |
| `src/custom_controlnet_aux/diffusion_edge/taming/modules/autoencoder/lpips/vgg.pth` | 7289 |
| `src/custom_controlnet_aux/mesh_graphormer/hand_landmarker.task` | 7819105 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_extra.npy` | 771808 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_h36m_correct.npy` | 937168 |
| `src/custom_mesh_graphormer/modeling/data/MANO_LEFT.pkl` | 3447713 |
| `src/custom_mesh_graphormer/modeling/data/MANO_RIGHT.pkl` | 3447679 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_indices.pt` | 21639 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_size.pt` | 173 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_values.pt` | 5663 |
| `src/custom_mesh_graphormer/modeling/data/mano_downsampling.npz` | 176509 |
| `src/custom_mesh_graphormer/modeling/data/mesh_downsampling.npz` | 1720359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_indices.pt` | 48423 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_size.pt` | 175 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_values.pt` | 12359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_faces.npy` | 21128 |

---

## Revision 1 report (retained; superseded above)

> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 64 of 64 converted; 39 tested (scoped), 4 converted but untested/partly tested,
> 21 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> (The 21 are converted in source but pending capability: 20 need original checkpoints staged and a model-load test; FaceMesh needs `mediapipe`.)

# ControlNet Aux — secure conversion report (in progress)

## Provenance

- Upstream: https://github.com/Fannovel16/comfyui_controlnet_aux
- Pinned commit: `0cd290477128d42cdc3e76a826a402d866e8c684` (key `x0cd2904`, tree `4f98bb6e32b99c4f8110bb7b4e4f24f7d2ec1760`)
- Converted tree: integrated candidate `full1613` (FaceMesh private-import fix), packaged unchanged except: model files excluded (below), private host paths in test helpers redacted, and this report updated.
- Mirror mode: original node ids, display names and categories; no `-Secure` suffixes.

## Per-node status (2026-10-15)

Dispositions: **tested** = scoped behavior evidence on the registered node; **converted-untested** / **partial** = source converted, positive behavior not (fully) tested; **pending-capability** = source converted but blocked on a capability (checkpoints, dependency).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| AIO_Preprocessor | AIO Aux Preprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `aio-shared-and-full-cli-original-dispatch-pass-r2` |
| AnimalPosePreprocessor | AnimalPose Estimator (AP10K) | pending-capability | Needs original checkpoint(s): bbox `yolox_l.torchscript.pt` / `yolox_l.onnx` (or `yolo_nas_{l,m,s}_fp16.onnx`) + pose `rtmpose-m_ap10k_256_bs5.torchscript.pt` / `rtmpose-m_ap10k_256.onnx`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| AnimeFace_SemSegPreprocessor | Anime Face Segmentor | pending-capability | Needs original checkpoint(s): `Annotators/UNet.pth` + `isnetis.ckpt` + torchvision `mobilenet_v2-b0353104.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| AnimeLineArtPreprocessor | Anime Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anime-shared-and-full-cli-original-model-pass-r1` |
| AnyLineArtPreprocessor_aux | AnyLine Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anyline-shared-and-full-cli-original-model-pass-r2` |
| BAE-NormalMapPreprocessor | BAE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `bae-shared-and-full-cli-original-model-pass-r1` |
| BinaryPreprocessor | Binary Lines | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| CannyEdgePreprocessor | Canny Edge | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ColorPreprocessor | Color Pallete | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ControlNetAuxSimpleAddText | ControlNetAuxSimpleAddText | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| ControlNetPreprocessorSelector | Preprocessor Selector | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| DensePosePreprocessor | DensePose Estimator | pending-capability | Needs original checkpoint(s): `densepose_r50_fpn_dl.torchscript` (option `densepose_r101_fpn_dl.torchscript`). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DepthAnythingPreprocessor | Depth Anything | pending-capability | Needs original checkpoint(s): `depth_anything_vitl14.pth` (vitb14/vits14 options); managed bundles LiheYoung/depth-anything-{large,base,small}-hf. Source converted; fails closed until assets are staged and a model-load test is approved. |
| DepthAnythingV2Preprocessor | Depth Anything V2 - Relative | pending-capability | Needs original checkpoint(s): `depth_anything_v2_vit{s,b,l}.pth` (depth-anything/Depth-Anything-V2-*); selected test asset `depth_anything_v2_vits.pth` (99.2 MB). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DiffusionEdge_Preprocessor | Diffusion Edge (batch size ↑ => speed ↑, VRAM ↑) | pending-capability | Needs original checkpoint(s): `diffusion_edge_{indoor,urban,natrual}.pt` + `swin_b-68c6b09e.pth` + `vgg16-397923af.pth` + LPIPS `vgg.pth` (upstream-tracked; excluded from v2). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DSINE-NormalMapPreprocessor | DSINE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `dsine-shared-full-cli-original-member-model-pass-r4` |
| DWPreprocessor | DWPose Estimator | pending-capability | Needs original checkpoint(s): bbox `yolox_l.onnx` (or torchscript / yolo_nas variants) + pose `dw-ll_ucoco_384_bs5.torchscript.pt` / `dw-ll_ucoco_384.onnx`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| ExecuteAllControlNetPreprocessors | Execute All ControlNet Preprocessors | converted-untested | Runs every child preprocessor; a full positive run needs every child checkpoint. Canonical 68-schema regeneration in progress (pinned SDK adds `Schema.loop_boundary`); the lazy raw-link ExecuteAll successor (R114) is NOT in this tree. |
| FacialPartColoringFromPoseKps | Colorize Facial Parts from PoseKPS | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| FakeScribblePreprocessor | Fake Scribble Lines (aka scribble_hed) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1` |
| HEDPreprocessor | HED Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1` |
| HintImageEnchance | Enchance And Resize Hint Images | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromImage | Generation Resolution From Image | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromLatent | Generation Resolution From Latent | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageIntensityDetector | Image Intensity | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageLuminanceDetector | Image Luminance | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| InpaintPreprocessor | Inpaint Preprocessor | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| LeReS-DepthMapPreprocessor | LeReS Depth Map (enable boost for leres++) | pending-capability | Needs original checkpoint(s): `res101.pth` + pix2pix `latest_net_G.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| LineArtPreprocessor | Realistic Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `lineart-shared-and-full-cli-original-model-pass-r1` |
| LineartStandardPreprocessor | Standard Lineart | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| M-LSDPreprocessor | M-LSD Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `mlsd-shared-and-full-cli-original-model-pass-r1` |
| Manga2Anime_LineArt_Preprocessor | Manga Lineart (aka lineart_anime_denoise) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `manga-shared-and-full-cli-original-model-pass-r1` |
| MaskOptFlow | Mask Optical Flow (DragNUWA) | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| MediaPipe-FaceMeshPreprocessor | MediaPipe Face Mesh | pending-capability | Needs the `mediapipe` dependency (not in the current 40-wheel private profile); its face-landmark model ships inside mediapipe. Private-core import fix is in this tree; constructor and positive behavior untested. |
| MeshGraphormer+ImpactDetector-DepthMapPreprocessor | MeshGraphormer Hand Refiner With External Detector | pending-capability | Needs original checkpoint(s): everything MeshGraphormer needs + an Impact-Pack detector (external pack integration). Source converted; fails closed until assets are staged and a model-load test is approved. |
| MeshGraphormer-DepthMapPreprocessor | MeshGraphormer Hand Refiner | pending-capability | Needs original checkpoint(s): `graphormer_hand_state_dict.bin` + `hrnetv2_w64_imagenet_pretrained.pth` + `hand_landmarker.task` + MANO/SMPL modeling data (upstream-tracked; excluded from v2). Source converted; fails closed until assets are staged and a model-load test is approved. |
| Metric3D-DepthMapPreprocessor | Metric3D Depth Map | pending-capability | Needs original checkpoint(s): `metric_depth_vit_small_800k.pth` (vit-large / vit-giant2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| Metric3D-NormalMapPreprocessor | Metric3D Normal Map | pending-capability | Needs original checkpoint(s): `metric_depth_vit_small_800k.pth` (vit-large / vit-giant2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| MiDaS-DepthMapPreprocessor | MiDaS Depth Map | converted-untested | Original Intel/dpt-hybrid-midas `pytorch_model.bin` (489.6 MB) cached; native forward and gVisor import/reader pass; learned guest forward approved, not yet run. |
| MiDaS-NormalMapPreprocessor | MiDaS Normal Map | converted-untested | Same model and gates as MiDaS-DepthMapPreprocessor. |
| OneFormer-ADE20K-SemSegPreprocessor | OneFormer ADE20K Segmentor | pending-capability | Needs original checkpoint(s): `250_16_swin_l_oneformer_ade20k_160k.pth`; managed bundle shi-labs/oneformer_ade20k_swin_large. Source converted; fails closed until assets are staged and a model-load test is approved. |
| OneFormer-COCO-SemSegPreprocessor | OneFormer COCO Segmentor | pending-capability | Needs original checkpoint(s): `150_16_swin_l_oneformer_coco_100ep.pth`; managed bundle shi-labs/oneformer_coco_swin_large. Source converted; fails closed until assets are staged and a model-load test is approved. |
| OpenposePreprocessor | OpenPose Pose | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `openpose-original7-HTTP-full1591-CLI-scoped-pass-r5` |
| PiDiNetPreprocessor | PiDiNet Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1` |
| PixelPerfectResolution | Pixel Perfect Resolution | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| PyraCannyPreprocessor | PyraCanny | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| RenderAnimalKps | Render Pose JSON (Animal) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| RenderPeopleKps | Render Pose JSON (Human) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| SAMPreprocessor | SAM Segmentor | pending-capability | Needs original checkpoint(s): `mobile_sam.pt`; managed effective default facebook/sam-vit-base. Source converted; fails closed until assets are staged and a model-load test is approved. |
| SavePoseKpsAsJsonFile | Save Pose Keypoints | tested | Scoped original managed-output pass on shared HTTP and full-source CLI — evidence: `savepose-shared-full-cli-original-json-scoped-pass-r4` |
| Scribble_PiDiNet_Preprocessor | Scribble PiDiNet Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1` |
| Scribble_XDoG_Preprocessor | Scribble XDoG Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ScribblePreprocessor | Scribble Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| SemSegPreprocessor | Semantic Segmentor (legacy, alias for UniFormer) | pending-capability | Needs original checkpoint(s): `upernet_global_small.pth` (UniFormer). Source converted; fails closed until assets are staged and a model-load test is approved. |
| ShufflePreprocessor | Content Shuffle | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TEEDPreprocessor | TEEDPreprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `teed-shared-and-full-cli-same-runtime-original-model-pass-r2` |
| TilePreprocessor | Tile | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileGF_Preprocessor | TTPlanet Tile GuidedFilter | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileSimple_Preprocessor | TTPlanet Tile Simple | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| UniFormer-SemSegPreprocessor | UniFormer Segmentor | pending-capability | Needs original checkpoint(s): `upernet_global_small.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| Unimatch_OptFlowPreprocessor | Unimatch Optical Flow | pending-capability | Needs original checkpoint(s): `gmflow-scale2-regrefine6-mixdata.pth` (scale1 / scale2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| UpperBodyTrackingFromPoseKps | Upper Body Tracking From PoseKps (InstanceDiffusion) | partial | Only limited empty / disabled / excluded tracking cases tested; full positive tracking cases open. |
| Zoe-DepthMapPreprocessor | Zoe Depth Map | pending-capability | Needs original checkpoint(s): `ZoeD_M12_N.pt`; managed bundle Intel/zoedepth-nyu-kitti. Source converted; fails closed until assets are staged and a model-load test is approved. |
| Zoe_DepthAnythingPreprocessor | Zoe Depth Anything | pending-capability | Needs original checkpoint(s): `depth_anything_metric_depth_{indoor,outdoor}.pt` (LiheYoung/Depth-Anything metric checkpoints). Source converted; fails closed until assets are staged and a model-load test is approved. |

### Test-only fixture nodes removed

The integrated candidate also registered two non-original MiDaS comparison fixtures (`AMY_Aux_MIDAS_Native_Input_R1`, `AMY_Aux_MIDAS_Same_Runtime_Original_Consumer_R1`). They, their entrypoint wrapper and the files that existed only for them (`_test_midas_first_fixture.py`, `_midas_first_original_native_golden.json`, `_test_midas_config.json`, `_test_midas_fixture_inputs.py`, `_test_midas_native_batch.py`, `_test_midas_native_detector.py`, `_test_midas_processor.json`, `tests/workflows/amy-aux-midas-original-first-r1.json`) are removed from this tree; `v2/__init__.py` now exports the 64-node entrypoint from `nodes.py`, and `secure-nodes.json` was regenerated by the SDK from this exact tree (64 original ids). The fixtures remain in the private test harness outside `v2/`.

## Refused techniques (never-do) and public replacements

| Refused technique | Public replacement in this conversion |
| --- | --- |
| Importing ComfyUI private core (`comfy.*`, `folder_paths`, model management) inside node code | Public `comfy_api.latest` `io` / `sdk` APIs; private-core references confined to test-only `_test_*` reference helpers |
| Downloading checkpoints at run time (Hugging Face Hub / torch.hub / URLs in `from_pretrained`) | Declared, SHA-256-pinned managed weights resolved by the host; no guest network |
| Unrestricted pickle loading of downloaded checkpoints | Managed loaders / restricted state-dict readers bound to pinned bytes |
| Writing files into the pack folder or arbitrary paths (SavePose JSON) | SDK managed `output` capability |
| Reaching into the executing prompt graph directly (ExecuteAll) | Public graph expansion (`enable_expand`) on the SDK node output |

## Pending (not yet supported — needs <capability>)

- 20 model-gated nodes: not yet supported — needs the original checkpoints staged in the managed model store plus an approved model-load test (per-node list above).
- MediaPipe-FaceMeshPreprocessor: not yet supported — needs the `mediapipe` dependency in the pack's private profile.
- MeshGraphormer (both nodes): not yet supported — needs MANO/SMPL modeling data and `hand_landmarker.task` delivered as managed assets (excluded from v2), plus the Impact-Pack detector for the Impact variant.
- ExecuteAllControlNetPreprocessors: canonical manifest regeneration under the current SDK and the lazy raw-link stage successor are not yet in this tree.

## Open test gates

- MiDaS learned guest forward (approved CPU-only run, not yet executed).
- ExecuteAll canonical 68-schema discovery (debug run: 60/66 retained schemas match after the SDK `loop_boundary` field; 6 still under investigation).
- SavePose empty-list error case on the registered node (prepared, not run).
- FaceMesh constructor and positive behavior; UpperBodyTracking full positive cases.
- All 20 model-gated families (checkpoint staging plan to be sent to the manager first).
- Whole-pack acceptance and normal registry publication: not started.

## Authority / permissions

| Permission set | Nodes |
| --- | --- |
| `raw` | 45 (AnimalPosePreprocessor, BinaryPreprocessor, CannyEdgePreprocessor, ColorPreprocessor, ControlNetAuxSimpleAddText, DWPreprocessor, …) |
| `raw`, `assets`, `models.download` | 15 (AnimeLineArtPreprocessor, AnyLineArtPreprocessor_aux, BAE-NormalMapPreprocessor, DSINE-NormalMapPreprocessor, FakeScribblePreprocessor, HEDPreprocessor, …) |
| `raw`, `assets` | 1 (AnimeFace_SemSegPreprocessor) |
| `assets`, `output` | 1 (SavePoseKpsAsJsonFile) |
| `raw`, `assets`, `models.download`, `output` | 1 (AIO_Preprocessor) |
| (none) | 1 (ControlNetPreprocessorSelector) |

## Assets / weights required (never committed)

Declared managed weights already in the canonical manifest (tested nodes):

| Node id | Declared weights |
| --- | --- |
| AIO_Preprocessor | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013); `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6); `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c); `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725); `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |
| AnimeLineArtPreprocessor | `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf) |
| AnyLineArtPreprocessor_aux | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| BAE-NormalMapPreprocessor | `scannet.pt` (lllyasviel/Annotators, sha256 03dbf1600c51) |
| DSINE-NormalMapPreprocessor | `dsine.pt` (hr16/Diffusion-Edge, sha256 629472c66ea9) |
| FakeScribblePreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| HEDPreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| LineArtPreprocessor | `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061) |
| M-LSDPreprocessor | `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c) |
| Manga2Anime_LineArt_Preprocessor | `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| MiDaS-DepthMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| MiDaS-NormalMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| OpenposePreprocessor | `body_pose_model.pth` (lllyasviel/Annotators, sha256 25a948c16078); `hand_pose_model.pth` (lllyasviel/Annotators, sha256 b76b00d17509); `facenet.pth` (lllyasviel/Annotators, sha256 8beb52e54862) |
| PiDiNetPreprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| Scribble_PiDiNet_Preprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| TEEDPreprocessor | `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |

Model-gated nodes need the checkpoints listed in the per-node table. Upstream-tracked model files excluded from `v2/` (still present in the pristine tree):

| File (upstream path) | Bytes |
| --- | --- |
| `src/custom_controlnet_aux/diffusion_edge/taming/modules/autoencoder/lpips/vgg.pth` | 7289 |
| `src/custom_controlnet_aux/mesh_graphormer/hand_landmarker.task` | 7819105 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_extra.npy` | 771808 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_h36m_correct.npy` | 937168 |
| `src/custom_mesh_graphormer/modeling/data/MANO_LEFT.pkl` | 3447713 |
| `src/custom_mesh_graphormer/modeling/data/MANO_RIGHT.pkl` | 3447679 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_indices.pt` | 21639 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_size.pt` | 173 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_values.pt` | 5663 |
| `src/custom_mesh_graphormer/modeling/data/mano_downsampling.npz` | 176509 |
| `src/custom_mesh_graphormer/modeling/data/mesh_downsampling.npz` | 1720359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_indices.pt` | 48423 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_size.pt` | 175 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_values.pt` | 12359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_faces.npy` | 21128 |

Redacted private host paths in 1 test helper file(s): `_test_openpose_same_runtime_original.py`.

---

## Historical report (retained; superseded by the per-node status above)

<!-- secure-conversion-report-v1 -->
# ControlNet Aux: conversion in progress

Upstream: https://github.com/Fannovel16/comfyui_controlnet_aux
Pin: `0cd290477128d42cdc3e76a826a402d866e8c684`

64 backend IDs; 27 helper drafts, nine previously trained CPU detector drafts and one unexecuted AnyLine composition draft; zero frontend extensions, JS-only nodes or routes. No complete-pack count.

## Backend node dispositions

| Exact node ID | Status | Evidence boundary |
| --- | --- | --- |
| AIO_Preprocessor | pending | Native parameter/default construction and pack-owned async dispatch drafted; selected unimplemented detectors remain fail closed; canonical SDK and registered guest proof pending |
| AnimalPosePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| AnimeFace_SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| AnimeLineArtPreprocessor | pending | Trained CPU/guest/outer IMAGE; default512 projected budget excluded, admitted profile/provisioning/device release gates pending |
| AnyLineArtPreprocessor_aux | pending | Four-mode source composition implemented; exact MTEED bytes acquired; native/trained/registered/profile tests not yet run |
| BAE-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| BinaryPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| CannyEdgePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ColorPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ControlNetAuxSimpleAddText | pending | Draft bundled-font annotation; first-image/quantization parity tested, release gate pending |
| ControlNetPreprocessorSelector | pending | Draft exact catalogue/pass-through; zero-capability guest tested, release gate pending |
| DSINE-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DWPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DensePosePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DepthAnythingPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DepthAnythingV2Preprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DiffusionEdge_Preprocessor | pending | Model/asset/graph port pending; draft fails closed |
| ExecuteAllControlNetPreprocessors | pending | Model/asset/graph port pending; draft fails closed |
| FacialPartColoringFromPoseKps | pending | Source pose-coloring CPU pixels through fresh guests and outer IMAGE; no detector inference claim |
| FakeScribblePreprocessor | pending | Trained CPU HED/scribble pixel parity through guests and outer IMAGE; provisioning/device release gates pending |
| HEDPreprocessor | pending | Trained CPU pixel parity through guests and outer IMAGE; provisioning/device release gates pending |
| HintImageEnchance | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageGenResolutionFromImage | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageGenResolutionFromLatent | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageIntensityDetector | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageLuminanceDetector | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| InpaintPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| LeReS-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| LineArtPreprocessor | pending | Trained fine/coarse CPU/guest/outer IMAGE; provisioning/device release gates pending |
| LineartStandardPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| M-LSDPreprocessor | pending | Trained source-wrapper CPU/guest/outer pixel parity; provisioning/device release gates pending |
| Manga2Anime_LineArt_Preprocessor | pending | Trained pinned CPU/guest/outer IMAGE; native256 rounding retained, default512 budget excluded, provisioning/profile/device gates pending |
| MaskOptFlow | pending | Exact flow visualization/masking through fresh guests and outer outputs; explicit BHW mask normalization and guest-local alias lifetime, full release gate pending |
| MediaPipe-FaceMeshPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MeshGraphormer+ImpactDetector-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MeshGraphormer-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Metric3D-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Metric3D-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MiDaS-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MiDaS-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OneFormer-ADE20K-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OneFormer-COCO-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OpenposePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| PiDiNetPreprocessor | pending | Trained source-wrapper CPU/guest/outer pixel parity; provisioning/device release gates pending |
| PixelPerfectResolution | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| PyraCannyPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| RenderAnimalKps | pending | Source first-frame pose rendering through fresh guests and outer IMAGE; no detector inference claim |
| RenderPeopleKps | pending | Source first-frame pose rendering through fresh guests and outer IMAGE; no detector inference claim |
| SAMPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| SavePoseKpsAsJsonFile | pending | Source JSON bytes/counter names through managed output, fresh guests and production outer; local output lifetime and cloud release gates pending |
| ScribblePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| Scribble_PiDiNet_Preprocessor | pending | Trained source-wrapper double-NMS CPU/guest/outer parity; provisioning/device release gates pending |
| Scribble_XDoG_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| ShufflePreprocessor | pending | Draft pure helper; seed/guest/outer behavior tested, release gate pending |
| TEEDPreprocessor | pending | Trained CPU pixels through fresh guests and outer IMAGE; NC artifact/provisioning/device release gates pending |
| TTPlanet_TileGF_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| TTPlanet_TileSimple_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| TilePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| UniFormer-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Unimatch_OptFlowPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| UpperBodyTrackingFromPoseKps | pending | Source tracking through fresh guests and custom outer TRACKING; integer keys and NumPy scalar coordinates preserved |
| Zoe-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Zoe_DepthAnythingPreprocessor | pending | Model/asset/graph port pending; draft fails closed |

## Observed evidence

The 20-helper suite passed 96 checks in 8.69 seconds, including two fresh guest roots/PIDs, raw denial for buffer operations, zero-capability selector execution, production manifest proxies and outer output typing, and independently lifted pristine algorithm differentials. The prior 19-helper checkpoint preserves 88 passing checks and both byte-exact roundtrips. The initial 87-pass/one-failure run incorrectly expected a scalar selector to require raw access; it is retained separately. Annotation uses the byte-exact bundled font, preserves first-image-only uint8 conversion, and bounds UTF-8 text before drawing. Shuffle preserves seeded content remapping, the source's render-local NumPy RNG use for seed zero, uint64 maximum seeds and native negative-seed failure; projected noise workspace is bounded before allocation. Progress notification is a recording double. PyraCanny retains the pinned constant-image divide/cast warnings. Tile retains native zero-dimension failures; guided tile retains its ignored resolution argument. Exact 64-node pristine CPU import and schema census were observed separately. Artifact gate remains in progress.

Python contract: generated `comfy-api.pyi` SHA256 a38c781f061321d0454044cd47ab30a227e2fbe81b196c229a8d1d6a0d0b0406. TypeScript contract: checked ModelFolder union SHA256 2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090. Their current provenance is coordinator-owned output artifacts, not a rewrite of the completed KJ pack.

Pose JSON output uses existing public managed output catalogue and text writer operations, with `assets` and `output` permissions only. It preserves admitted source JSON bytes, counter names, width/height/time substitutions, empty-prefix names and the declared zero-output contract. JSON structure, encoded bytes, catalogue size, filename size and collision retries are bounded before the corresponding work. Native empty/missing-key and non-JSON errors have source controls. Nonfinite numbers, cycles, excessive structures and unsafe logical prefixes fail before output. Time substitution is tested with a controlled local clock; cross-server clock/timezone equivalence is unproved.

The catalogue enumerates managed files, whereas the original filesystem counter can also count directory names. Existing files are preserved by `new_only` writes and at most 32 collision retries; the source can overwrite after a race. Invalid JSON is rejected before creating a file, while the original can leave a partial file. These are explicit managed-output lifetime and namespace adaptations. The existing text writer does not promise atomic publication or a transaction across files. Tests use local output backing and actual guest/outer dispatch with a fixture execution backend. They do not establish cloud storage continuity, import/download delivery, Windows naming parity or aggregate resource enforcement. All 64 release dispositions remain pending.

HED and Fake Scribble passed seven focused checks, including four trained original-source CPU pixel comparisons, both safe modes, grayscale/RGB/RGBA inputs, batches, two fresh guest roots/PIDs, asset/raw denials and production manifest proxies with outer IMAGE outputs. The actual restricted weight loader, tensor transport and pack-owned network execute without model/math doubles. The operator catalogue and execution backend are test fixtures; automatic provisioning and deployed sandbox execution were not observed. Wrong-digest and projected-network-workspace checks fail before model construction.

The declared artifact is `lllyasviel/Annotators` at revision `982e7edaec38759d914a963c48c4726685de7d96`, file `ControlNetHED.pth`, SHA256 `5ca93762ffd68a29fee1af9d495bf6aab80ae86f08905fb35472a083a4c7a8fa`. Its 29,444,406 bytes were verified before default restricted loading; the closed state contains 37 float16 tensors. The pack loads exact keys strictly into its source-derived CPU network. Node execution resolves and verifies managed assets; acquisition belongs to the declaration/provisioning layer. The model card declares license `other`, which does not establish commercial deployment clearance.

PiDiNet, Scribble PiDiNet and M-LSD passed ten focused checks. Six independent original-wrapper comparisons cover both PiDiNet safe modes, the scribble wrapper's second NMS/blur stage, M-LSD threshold modes and grayscale/RGB/RGBA inputs. Each case traverses two fresh actual guests with asset/raw denials and the production manifest outer IMAGE path. Direct trained network-forward checks ensure M-LSD's native catch-all does not conceal an untested network. Algorithm and constructor AST comparisons preserve the pinned code; the unused MobileNet pretrained-backbone downloader is deliberately refused, while the used constructor retains `pretrained=False`. Offline provisioning identity, CPU device selection and progress are oracle doubles; model state/math, restricted loading and guest tensor transport are real. An initial missing Enum in the source-lifting fixture caused seven failures before comparison, retained separately; adding the omitted source import corrected the harness.

Both additional artifacts use the same pinned Annotators revision: `table5_pidinet.pth`, 2,871,148 bytes, SHA256 `80860ac267258b5f27486e0ef152a211d0b08120f62aeb185a050acc30da486c`; and `mlsd_large_512_fp32.pth`, 6,341,481 bytes, SHA256 `5696f168eb2c30d4374bbfd45436f7415bb4d88da29bea97eea0101520fba082`. Checksum verification preceded default restricted loading. The canonical loader selects PiDiNet's `state_dict` and excludes epoch metadata before guest admission; its 83 tensor keys then undergo the exact upstream module-prefix normalization. M-LSD strictly loads all 362 tensor keys, including batch-normalization integer counters. No unsafe loader, downloaded code, key filtering or new shared API is used.

TEED declares `bdsqlsz/qinglong_controlnet-lllite` revision `67006a35a5955437d118490bfec822402eff09f5`, file `Annotators/7_model.pth`, SHA256 `b9037964149c55156c6adbffdfbd7e8ca7d2ef2a4d90573520efa7f3a1aacf06`. Its 247,232 bytes were verified before default restricted loading; all 36 floating tensor keys load strictly. Pinned network and detector math remain pack-owned; removing the local smish JIT decorator avoids execution-time compilation. Tests compare against the original scripted activation, including trained logits before quantization and pixel outputs across safe-step settings, channels and dtypes. Actual fresh guest roots/PIDs and production manifest outer IMAGE checks use real weights, assets and tensor transport with raw/assets denial. Operator catalogue, progress and execution backend are fixtures; no automatic provisioning, GPU or cloud claim. The card declares CC BY-NC-SA 4.0; technical testing does not establish commercial deployment clearance. The initial outer failure from stale manifest asset permissions is retained; manifest regeneration resolves it without relaxing capability checks.

Realistic fine/coarse and anime line-art passed seven focused checks, including strict original architecture/call AST comparisons, four trained CPU pixel cases across channels/dtypes, both realistic model choices, two fresh actual guest roots/PIDs, raw/assets denial and declared outer IMAGE outputs. No model/math doubles are used; operator catalogues, progress and execution backend remain fixtures. Artifacts use the reviewed Annotators revision: `sk_model.pth` SHA256 `c686ced2a666b4850b4bb6ccf0748031c3eda9f822de73a34b8979970d90f0c6` and `sk_model2.pth` SHA256 `30a534781061f34e83bb9406b4335da4ff2616c95d22a585c1245aa8363e74e0`, each 17,173,511 bytes/24 tensors; `netG.pth` SHA256 `ccabdcc3f5cf3c07cf65d58776acb21df7dfda825cdc70c9766a93fd62bfc488`, 217,631,959 bytes/32 tensors. Hash verification precedes default `weights_only=True` CPU parsing. The initial ZIP-only globals scanner limitation is preserved; default restricted legacy-stream parsing succeeds without aliases or unsafe fallback. Anime preserves the exact upstream module-prefix normalization and extra resize to multiples of256. Its conservative projected budget excludes default512 and other larger workloads; small64-resolution trained evidence does not certify them. These work estimates are not hard per-realm RAM/VRAM enforcement. Artifact provisioning, admitted compute profiles, GPU and commercial deployment clearance remain unresolved.

## Limits and persistence

Four pose helpers passed 18 focused checks twice (10.13/10.63 seconds). Independent lifted pristine algorithms cover normalized/pixel coordinates, missing points, facial point/polygon modes, native malformed cases, first-frame-only rendering and in-process source tracking mutation. All four traverse two fresh actual guest roots/PIDs and production manifest outer IMAGE/TRACKING outputs. Inputs are bounded before allocation. Initial failures separately preserve an outer-test fixture mistake and an actual shared transport loss of integer tracking keys/NumPy scalar coordinates. The unchanged behavior assertions pass after the generic transport repair; neither detector inference nor pose-file durability is established.

Manga line-art adds six focused checks: exact nine architecture class ASTs and detector call AST, trained RGB/gray/RGBA and batch/dtype pixel comparisons, two fresh actual guest roots/PIDs, raw/assets denial, two manifest-driven outer IMAGE cases, digest rejection and pre-allocation validation using the native ceiling to multiples of256. `erika.pth` at the same immutable Annotators revision is 172,789,563 bytes, SHA256 `badbd6baf013cefbd98993307b02cc14a26c770d067416e4fdecc8720b88feeb`; checksum and unchanged metadata precede default restricted CPU loading of707 tensors/172,540,124 tensor bytes. Batch-normalization integer counters are retained, all707 source-normalized keys load strictly, and pinned substring `module.` normalization is unchanged. No tensor filtering, unsafe parser, algorithm/model double or new inference API is used. Operator catalogue and execution backend remain fixtures. Conservative workspace estimates exclude default512; the observed64-resolution cases invoke the original256-rounded internal network and do not certify larger workloads or hard RAM/VRAM enforcement. Card license `other`, provisioning, managed compute profiles and GPU release remain unresolved.

Trained HED, Fake Scribble, PiDiNet, Scribble PiDiNet, M-LSD, TEED, both line-art and manga line-art CPU inference paths are observed within the tested cases. Automatic weights provisioning, GPU/device-policy parity and cloud deployment remain unverified. Twenty-nine model/graph/pose branches remain unimplemented and fail closed. V2 entry import omits ambient environment/sys.path mutation and runtime installers. Unported sources remain review input, not admitted execution. Editable config, cloud pose-output persistence and other model artifacts remain pending. Python 3.13 is the managed runtime tested here.

Optical-flow masking adds 28 focused checks. Three pure visualization functions and the masking class retain their pinned ASTs, removing only the ambient helper import. Exact FP32/FP64/FP16 pixels, resizing, mask truncation, local input mutation and native BF16 failure are covered. The source requires N1HW masks and fails on canonical BHW MASK input; the port explicitly adds the channel dimension before unchanged math. Flow visualization's unknown-value clearing and masking mutate the local tensor as in source. Actual guest and outer execution return exact results while host input remains unchanged, an explicit guest-local alias normalization. Four admitted cases and four raw denials across two fresh required Seatbelt guests plus manifest-driven outer custom OPTICAL_FLOW/IMAGE outputs use real tensor transport. The initial 27-pass/one-failure test expected a different raw-denial message; the retained log is corrected only to the observed permission error. No weights, model inference, new shared API, heap/profile grant or cloud claim. Projected visualization workspace is bounded before work. Thirty model/graph/pose branches remain unimplemented; all 64 release dispositions remain pending.

## Selection provenance

Historical Aug4 download rank8/2,507,966downloads. Registry SHA a0f27ea0f7b4ae1b26f2cf84b72ab3b2ad06eb4eb1f3aed7a338a4a2b1d47408. No current trending claim. HARVEY conditional static gains remain separate.

## AMY AnyLine successor

The complete original 64-ID schema is unchanged. AnyLine now declares exact MTEED plus fine/coarse/anime/manga artifacts and uses the existing pack-owned managed loaders. It retains first-channel inclusive intensity masking, three-dimensional morphology over HWC, composition arithmetic, source mode spelling and native incompatible-size failures. Existing inherited workload bounds remain; default resolutions are not newly admitted by this source change. Canonical manifest regeneration/validation against the selected SDK and actual native/registered inference are pending. No raw filesystem model loading or source-import fallback exists in the converted code.

## Isolated AIO source successor

The original AIO helper now preserves `none` image identity and dispatches through the source AUX registry using the unchanged pinned input metadata. Required/optional merge order, explicit defaults, numeric fallback, absent combo defaults, and the upstream unhashable-list TypeError remain exact. The selected converted node retains its original workload validation and detector arithmetic. The helper contains no provider, artifact fallback, new detector, or source import fallback.

AIO declares the union of the existing AUX class permissions and nine existing weight records. The source AUX registry includes schema-excluded output/pose/flow entries; the unchanged AIO schema still exposes the original 47 choices including `none`. These declarations do not admit permissions or a runtime profile. Every unsupported selected detector still reaches its existing fail-closed branch. Canonical SDK manifest regeneration/equality, actual native and registered comparisons, model restricted-load admission, and separately fitting finite Linux/gVisor profiles remain future gates. Ten new stdlib source controls passed; they did not import scientific/SDK/vendor modules or execute inference. All 64 release gates remain pending.
