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
verified by the host, and read with `assets.load_state_dict`. The digests are
the Hugging Face LFS object ids at the pinned revisions — the publisher's own
hashes. The catalogue is the host-owned `geometry_estimation` folder, never a
path.

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

## Verification

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
