# Secure conversion ledger

- Upstream: https://github.com/SparknightLLC/ComfyUI-WeightedRandomChoice
- Pin: `a1ad37491ac0d5b89793c6ca3fea7de2b4b93155` (`xa1ad374`).
- Actual census: one Python node `WeightedRandomChoice`; zero frontend/JS-only
  nodes or routes. All supported; none rejected or pending.
- Exact display, chance/seed schema, optional wildcard sockets and unnamed ANY
  output retained. Upstream omits CATEGORY; `sd` is the actual host default.
- Pack-local seeded RNG preserves the exact decision without mutating process RNG.
  Selected scalar/container/ref is returned unchanged; missing-side defaults
  preserve the string/int/float/bool behavior. Legacy both-missing bare empty
  result is normalized into its intended single ANY output.
- Public ref mode, zero permissions. Opaque image/model/etc. refs are selected
  without materializing tensors or host objects. No private constructor in pack
  code, no files/network/models/storage/raw/graph/frontend authority.
- Bounds: finite chance 0..1, uint64 seed, recursive containers depth32/4096
  items and 64 KiB combined UTF-8. Malformed/cyclic/excessive input fails closed.
- Persistence: no durable pack state. Workflow-owned values/seed/chance only;
  fresh pack filesystem and guest continuity tested. No KV claim is needed.
- Upstream references `LICENSE.txt` but does not ship it; metadata retained,
  missing-license provenance documented rather than fabricated.
- Canonical d.ts `4a49be64…`, pyi `50848a56…`; no shared API or dependency gap.
- Final focused/shared gate: 72 tests (39 focused plus 33 patch/manifest
  regressions), twice on final bytes. Includes 240 seed/chance/default scalar
  cases, 1,000 randomized decisions, bounded/malformed/cyclic inputs, 144 scalar
  guest executions across original/fresh workers, image/latent ref passthrough,
  zero-capability raw denial, exact schemas/manifests and byte-exact roundtrip.
  No hardware or credential-dependent algorithm is present.

  `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider -q packs/comfyui-weightedrandomchoice/xa1ad374/ComfyUI-WeightedRandomChoice-HEAD/v2/tests/test_weighted_choice_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short`
