# Secure conversion ledger

- Upstream: https://github.com/throttlekitty/SDXLCustomAspectRatio
- Pin: `4a0bbec07134768324b49f14b2fa7f3bee66f0ba` (`x4a0bbec`).
- Actual imported standalone-module census: one Python `SDXLAspectRatio`, zero
  frontend/JS-only nodes or routes. One supported, zero rejected/pending.
- Exact node/display ID, image category, 28 ordered combo choices and two named
  INT outputs (`Width`, `Height`). First regex dimension match and 1024 fallback
  retained, including uppercase X, Unicode decimal digits, whitespace, zero
  direct dimensions and source-label inconsistencies (no invented corrections).
- `algorithm.py` is a byte-identical copy of pinned SDXLAspectRatio.py, CRLF
  included. Public value mode, zero permissions; no files/network/storage/raw/
  tensors/models or host imports. No shared API or dependency gap.
- Bounds: 64 KiB UTF-8 input, signed-64-bit nonnegative output values; native
  integer-string parsing errors retained. Oversized/malformed input fails closed.
- Persistence: no durable state. Choices/text are workflow inputs; fresh pack
  filesystem and isolated guest continuity are tested. No KV claim needed.
- Upstream references a license file in metadata but none is shipped; absence is
  documented rather than inventing terms. No hardware/credential path.
- Canonical d.ts `4a49be64…`, pyi `50848a56…`; exact patch roundtrip required.
- Complete focused/shared gate: 79 tests (46 focused plus 33 shared patch and
  manifest regressions), twice on final bytes. All 28 presets, 13 direct cases,
  500 seeded adversarial dimension strings, native integer errors, bounds and
  raw substitution denial are covered. Original and recreated filesystems run
  82 zero-capability guest executions with distinct worker PIDs.

  `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider -q packs/sdxlcustomaspectratio/x4a0bbec/SDXLCustomAspectRatio-HEAD/v2/tests/test_sdxl_aspect_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short`
