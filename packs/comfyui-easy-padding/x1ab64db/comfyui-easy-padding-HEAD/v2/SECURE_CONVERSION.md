# Conversion ledger

- Upstream: https://github.com/ealkanat/comfyui-easy-padding
- Exact pin: `1ab64dbce7420fc09400cfe7d5563a42e4250f7d`; release `x1ab64db`.
- Python: 1 supported, 0 rejected, 0 pending.
- Frontend: 0 supported, 0 rejected, 0 pending; 0 routes/JS-only nodes.
- Authority: public `SDK_REFS=False` value mode, `raw` only; no private ref API.
- Algorithm byte-identical to pristine node.py, license byte-identical.
- Exact schemas, batch padding, alpha conversion, clipping/quantization,
  inclusive mask rectangle, color parsing and transparent color bypass preserved.
- Bounds cover finite floating RGB/RGBA layouts, batch/dimensions, padding
  types/ranges, color-string length, and padded aggregate pixels before Pillow
  allocation. Invalid one-pixel squeeze semantics fail closed.
- Evidence: differential pixel/mask matrix and malformed/resource rejection,
  repeated-input/RNG isolation, real guest and outer IMAGE/MASK typing with raw
  denial, manifest/census/stub hashes, pristine identity and exact patch roundtrip.
- CPU behavior is proven; GPU-specific input/device execution is not exercised.
- No API/dependency gap or shared edits. Canonical d.ts `4a49be64…`, pyi `50848a56…`.
- Complete focused/shared gate: 120 tests on each of two final-byte runs;
  87 pack-focused tests plus 33 manifest/packpatch regressions. Only the external
  Torch/pynvml deprecation warning. Owned Python source/tests pass Ruff.
