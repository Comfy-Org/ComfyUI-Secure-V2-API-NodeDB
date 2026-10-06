# Conversion ledger

- Upstream: https://github.com/theshubzworld/ComfyUI-SD3.5-Latent-Size-Picker
- Exact pin: `67eeeeff12f5f6859a0f4c4853e14cc96a9dc8fe`; release `x67eeeef`.
- Actual loader census: 2 Python nodes supported, 0 rejected, 0 pending;
  0 frontend extensions, 0 JS-only nodes, 0 routes.
- Ownership: this pristine snapshot, its `v2/` sibling, and its exact patch pair.
- Preserved: exact IDs, display names, categories, input order/defaults/bounds,
  all 11 SD3.5 and 72 Flux preset choices, dimension overrides, inversion,
  aspect locks, cell rounding, channels, zero float32 outputs and named slots.
- API: public `sdk.LatentRef.empty`; SDK_REFS=True; no permissions. No private
  constructors or host imports. No new generalized primitive required.
- Bounds: existing host allocator batch 1–64 and 16,777,216 elements;
  pack-side integer/type validation and 1024-character resolution strings.
  The unchanged legacy batch max 4096 is a schema compatibility choice, not
  an execution grant. Excessive or malformed direct inputs fail closed.
- Provenance: upstream pyproject references LICENSE, but the pinned repository
  contains no LICENSE file. No license terms are invented or assigned here.
- Evidence: pristine differential dimension/zero-tensor matrices, exact schemas
  and census, real isolated zero-capability guest, allocation denial before ref
  creation, manifest/stub/security audit, cache hygiene, and byte-exact patch
  generation/apply/tree validation. Complete focused/shared gate: 72 passed
  on each of two required runs, with only the external Torch/pynvml warning.
- Command: `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python
  -m pytest -q -p no:cacheprovider v2/tests/test_sd35_latent_secure_conversion.py`
  plus `backend/tests/test_packpatch.py` and `backend/tests/test_packdb_manifest.py`
  from the secure runtime repository. Owned Python source/test Ruff checks pass.
