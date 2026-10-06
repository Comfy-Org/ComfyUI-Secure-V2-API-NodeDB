# Secure conversion ledger

- Upstream: https://github.com/jupo-ai/comfy-aspect-ratios
- Pin: `c47658e30eb82fef27cb7342793206b8606e9388` (`xc47658e`).
- Actual imported V3 entrypoint: one Python node
  `jupo.AspectRatios.AspectRatios`; one frontend extension; two POST routes.
  One Python and one frontend supported, zero rejected/pending. V2 has no routes.
- Exact schema, seven inputs, 16 ordered presets, latent/width/height outputs,
  category and display preserved. Original scalar calculation AST is identical;
  all three fixed-side modes, LCM floors, portrait ties and step rounding remain
  pack-side. Backend intentionally ignores preset: the UI updates ratio inputs.
- Zero backend and frontend permissions. Public `LatentRef.empty` replaces
  host-device lookup/Torch allocation. The latent cell geometry is explicitly
  floored before allocation, including direct non-eight-aligned steps. Returns
  original computed width/height and exact zero float32 sample shape. The broker
  adds canonical `downscale_ratio_spacial` metadata, absent from upstream.
- Bounds: base 64–8192, step 8–8192, ratio parts 1–4096, batch 1–64;
  projected output edges 8–8192 and 16,777,216 latent elements before allocation.
  Unknown options, bools and malformed controls fail closed. Legacy zero-cell
  allocations and unbounded control/batch values are deliberately not admitted.
  Static UI schema remains exact rather than silently changing its maxima.
- Frontend route math runs locally. Typed widget changes and an owned 82px mount
  replace callback/prototype mutation, fetch and ambient DOM/CSS injection.
  Preset changes, none no-op, ratio swap, live readout, workflow restoration,
  two-node isolation, removal and remount listener cleanup are tested.
- Persistence disposition: no durable state. Controls travel in the workflow;
  the result is derived. Fresh pack filesystem and guest workers preserve
  same-input results; no KV or cloud filesystem durability claim is made.
- MIT LICENSE copied byte-for-byte; all pristine files retain pinned Git bytes.
  Canonical d.ts `4a49be64…`, pyi `50848a56…` remain unchanged.
- Evidence: exact census/schema/route/function AST; 54 geometry cases, 1,000
  randomized Python/JS differentials plus all preset ratios; 36 real confined
  zero-capability guest executions across original/fresh roots with exact
  shape/dtype/zeros and preallocation denials; isolated VM frontend lifecycle,
  authoritative TypeScript contract check; manifest, security and byte-exact
  pristine→V2 patch/tree reconstruction. Complete focused/shared gate: 92/92
  twice on final bytes (59 focused plus 33 shared). The explicit per-ID
  `node-support.json` references node tests, not a whole-workflow claim.
  CPU is exercised; GPU allocation
  placement is broker-owned and not directly hardware-tested. No API gap.

Command: `PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -p no:cacheprovider -q packs/comfy-aspect-ratios/xc47658e/comfy-aspect-ratios-HEAD/v2/tests/test_jupo_aspect_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short`
