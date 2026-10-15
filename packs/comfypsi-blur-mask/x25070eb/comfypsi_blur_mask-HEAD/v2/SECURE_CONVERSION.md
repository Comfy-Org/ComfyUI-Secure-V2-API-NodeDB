# Secure conversion ledger

- Upstream: https://github.com/rookiepsi/comfypsi_blur_mask
- Pin: `25070eb27c9e938745c167edae428e5986c81cc1` (`x25070eb`).
- Actual census: one Python node (`comfypsi_blur_mask`), one frontend extension
  (`comfypsi.blur.mask`), no JS-only nodes or routes; all supported.
- Exact ID, display, category, MASK output and FLOAT defaults/bounds/step retained.
- Gaussian kernel construction, zero padding, dtype/device, tiny-mask behavior,
  batch/noncontiguous handling and nonpositive-blur identity remain pack-owned.
  `algorithm.py` and GPLv3 LICENSE are byte-identical to the pinned source.
- Backend: public value mode, `raw` only; no private constructors or host imports.
  Frontend: one typed onCreated width hook, idempotent install/dispose; no DOM,
  canvas, global input, storage or network authority. No frontend permission.
- Bounds: BHW floating finite masks, 1–64 batch, dimensions 1–8192, 16,777,216
  elements, positive blur at most 100, convolution work at most 268,435,456.
  Valid nonpositive direct blur values preserve the upstream identity path.
- Persistence: no durable pack state. Inputs are workflow-owned; no endpoints,
  files, caches or global counters. Fresh filesystem/guest recomputation is tested;
  no KV durability claim is needed.
- GPU-specific device execution is not directly exercised; CPU float32/float64,
  real isolated guests, raw denial and outer MASK tensor typing are tested.
- No shared API or dependency gap. Current canonical d.ts `4a49be64…` and pyi
  `50848a56…` are byte-pinned. Exact pristine→V2 patch roundtrip is required.
- Complete focused/shared gate: 97 tests (64 focused plus 33 patch/manifest
  regressions), twice on final bytes; frontend VM behavior, syntax and canonical
  TypeScript checking are embedded. Run from the corpus root:

  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/ben/comfy/ComfyUI_secure_nodes/backend/tests:/Users/ben/comfy/ComfyUI_secure_nodes/backend:/Users/ben/comfy/ComfyUI-secure-nodes /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q -p no:cacheprovider --confcutdir=packs/comfypsi-blur-mask/x25070eb/comfypsi_blur_mask-HEAD/v2 --rootdir=. packs/comfypsi-blur-mask/x25070eb/comfypsi_blur_mask-HEAD/v2/tests/test_blur_mask_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py`

  The confcutdir prevents pytest from importing the pristine snapshot's
  package entrypoint as a top-level test module; pristine package imports are
  instead performed explicitly in the differential/census tests.
