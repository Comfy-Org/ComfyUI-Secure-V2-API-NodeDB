# Secure conversion ledger

- Upstream: https://github.com/drustan-hawk/primitive-types
- Pin: `1b2d984818b26a0ea7f1394004e81f9286684b71` (`x1b2d984`).
- Actual loader census: four Python registrations (`int`, `float`, `string`,
  `string_multiline`); zero frontend extensions, JS-only nodes or routes.
  All four converted; no rejected or pending items.
- Exact IDs, display names, category, numeric range/default/step/number display,
  single/multiline defaults and unnamed output types retained. Scalar values
  pass through unchanged (including FLOAT integer values and signed zero).
- Public value mode, zero permissions. No shared API or dependency gap, host
  imports, private constructors, files, network, model, raw, storage or UI authority.
- Text direct inputs are bounded to 64 KiB UTF-8. Numeric inputs are finite,
  non-bool and within the existing schema bounds. Malformed calls fail closed.
- Persistence disposition: no durable pack state. Values are workflow inputs;
  fresh pack-filesystem/fresh isolated guest executions test continuity. No KV
  durability claim is needed. There is no hardware or credential-dependent path.
- LICENSE is copied byte-for-byte. Canonical d.ts `4a49be64…`, pyi `50848a56…`.
- Validation covers schema/census, scalar/type/identity differentials, seeded
  randomized inputs/RNG isolation, bounds, real zero-capability guests for all
  four nodes, raw substitution denial, manifests and exact patch roundtrip.
- Complete focused/shared gate: 78 tests (45 focused plus 33 shared patch and
  manifest regressions), twice on final bytes. Run from the corpus root:

  `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider -q packs/primitive-types/x1b2d984/primitive-types-HEAD/v2/tests/test_primitive_types_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short`
