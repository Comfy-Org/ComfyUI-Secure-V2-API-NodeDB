# ComfyUI-DepthAnythingV2 Secure Nodes V2 conversion ledger

Source tuple: `comfyui-depthanythingv2`,
`https://github.com/kijai/ComfyUI-DepthAnythingV2`,
`553187872eeb1d52e50dc53209fa57e569609a72`, `x5531878`.

Exact source census: **2 registered backend node IDs, 0 frontend
registrations, 0 routes.** Upstream is 1,539 lines, of which 1,347 are the
vendored DepthAnythingV2 architecture and 192 are the two nodes.

## Backend ledger

- `DownloadAndLoadDepthAnythingV2Model` — **supported**.
- `DepthAnything_V2` — **supported**.

Backend tally: **2 supported, 0 pending, 0 security-rejected.**

## Frontend ledger

Upstream ships no `web/` or `js/` directory. 0 supported, 0 pending,
0 rejected.

## What changed and why

No new API surface. This is the declared-weight pattern already used by the
Impact Subpack and Florence2 conversions: **the architecture stays in the
pack, and core only brokers pinned weights.**

**Weights.** Upstream called `snapshot_download` against a moving `main` ref
and wrote into an arbitrary `models/depthanything` directory, then read the
file back off disk. All nine checkpoints are now declared as
`sdk.HuggingFaceWeight` with a pinned 40-character repository revision and a
SHA-256, fetched on demand through `models.download_huggingface_weights`,
verified by the host, resolved to an asset with `assets.resolve`, and read with
`assets.load_state_dict`. The digests are the Hugging Face LFS object ids at
the pinned revisions — the publisher's own hashes. The catalogue is the
host-owned `geometry_estimation` folder, never a path.

**The DAMODEL handoff.** Upstream passed a live `torch.nn.Module` between its
two nodes inside a dict. That cannot cross a process boundary — and it never
needed to. What the second node actually requires is *which checkpoint, at
what precision*, which is plain data. `DAMODEL` now carries exactly that, and
the module is built or reused inside the guest keyed by the same description.
The guest process is per-pack and per-tenant, so the cache dies with it.

**Two host imports inside the vendored architecture.** Both were replaced with
pack-side equivalents in `depth_anything_v2/_ops.py`, and both are *proven*
equivalent rather than assumed:

- `comfy.ops.manual_cast` → `manual_cast.Linear` / `.Conv2d`, which cast
  weight and bias to the input's dtype and device exactly as core's
  `comfy_cast_weights` path does. Only these two layer types are used
  (`Conv2d` 16 times, `Linear` 3 times).
- `comfy.ldm.modules.attention.optimized_attention` → the same
  `scaled_dot_product_attention` path core's default backend takes, including
  the output reshape. The architecture only ever calls it with
  `skip_reshape=True`, no mask.

Backend selection is a host-wide policy and is deliberately not something a
depth model reaches for; the pack takes core's default rather than choosing.

**Dependencies dropped.** `huggingface_hub` is no longer imported (the host
performs the pinned fetch) and `torchvision`'s `Normalize` is inlined as the
broadcast subtract-and-divide it is, so the pack declares no dependencies.

**One correction.** Upstream's autocast guard checked only MPS; CPU with a
non-fp32 dtype would have entered `torch.autocast("cpu", torch.float16)`.
The converted guard covers that case. On CUDA the behaviour is identical.

## Repair r1: loading the weight

- **Asset reference.** The loader passed the catalogue name returned by
  `models.download_huggingface_weights` straight to
  `assets.load_state_dict`. That call takes an AssetRef, so every load failed.
  The name is now resolved with `assets.resolve(weight.folder, installed)` and
  the resulting reference is loaded.
- **Capabilities.** The host grants `models.download` only for weights a node
  declares, and requires `assets` for `assets.resolve` and
  `assets.load_state_dict`.
  - The loader now declares its nine weights (`SDK_REQUIRED_WEIGHTS`) and
    `models.download` and `assets`.
  - The depth node declares `assets`. It only rebuilds the module after a
    cache miss, for example in a new guest process. It then reads the weight
    the loader installed, under the same catalogue name, and never downloads.
- **Output image.** The depth image is created with the public
  `ImageRef.from_value` in place of the private `_from_raw`. This sets the
  minimum guest base to 0cd9adec. `from_value` refuses non-finite pixels. The
  original's NaN output for a perfectly flat depth map (0/0 in its
  normalisation) is therefore refused rather than passed on.

## Verification

`tests/test_dav2_weight_resolution.py`, run in the lane gate on both guest
bases, covers the loading path end to end.
- **What it runs:**
  - the loader node, then the depth node, then the depth node again after a
    cache miss;
  - the real in-process SDK, called as Core calls an SDK node;
  - a synthetic SafeTensors weight installed where the host's download puts
    it, with that one declaration pointed at the fixture.
- **What it checks:**
  - the loaded parameters equal the fixture;
  - the depth image is finite, BHWC and in [0, 1];
  - the rebuild after a cache miss uses only `assets.resolve` and
    `assets.load_state_dict` and gives the same bytes;
  - every capability those calls need on the overlay host (read from its
    handlers) is granted by the committed manifest rows;
  - the manifest equals the real encoder's output.
- **Before the repair:** against the published pack, the same test fails at
  the asset load and finds the missing capabilities.

The original conversion's suite:

`backend/tests/test_depthanything_pack_conversion.py` — 90 tests: exact
census, schema, dropdown order and defaults, and sealed manifest; every one of
the nine checkpoints asserted pinned, hash-verified, safetensors-only and
catalogue-confined; refusal of an undeclared checkpoint including a traversal
attempt; an AST proof that no guest module — vendored architecture included —
imports a host module, against five pristine files that do; **equivalence of
the cast layers to core's real `comfy.ops.manual_cast` across five
weight/input dtype combinations with and without bias**; **equivalence of the
attention shim to core's real `optimized_attention` across three head/dim
shapes**; encoder and metric-depth selection for all nine checkpoints;
precision resolution across all nine × four settings; the full inference
pipeline against upstream's transcribed `process()` over four image
geometries × two batch sizes × metric and relative modes; normalisation
against torchvision; cache keying; and distribution-pair reconstruction.

Not covered here: inference against the real 1.3 GB weights, which needs a
GPU host. The pipeline differential uses a deterministic stand-in network, so
what is proven is the conversion's own arithmetic, not the model's.
