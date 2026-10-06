# SizeFromArray — Secure Nodes V2

Upstream https://github.com/ITurchenko/ComfyUI-SizeFromArray at
`ba3a407af84a9446ebf0f9eb8cb38379953ad5a1` (`xba3a407`).
Census: 1 Python supported, 0 rejected, 0 pending; 0 frontend/JS-only nodes/routes.

The pack retains its comma/newline parsing and seeded
`numpy.random.default_rng(seed).choice` algorithm. Input order, duplicate weights,
ignored extra columns, whitespace/empty-line behavior and malformed-input errors
remain unchanged. Outputs are converted from NumPy scalars to Python integers
for wire transport without changing values. Schemas, names, defaults, bounds,
category and description are preserved.

Removed unused csv/os/Torch/ComfyUI/folder_paths imports and unused presets_dir.
There was no actual preset-file read to migrate. This is ordinary value-mode
computation with no capabilities, raw tensors, filesystem/network access, global
RNG reseeding or shared API additions. Per-call NumPy generators keep instances
and users independent. NumPy 2.4.x is declared; comparisons use installed 2.4.6.

Input text is bounded to 1 MiB UTF-8 and 4,096 nonempty rows before parsing or
array allocation. Larger requests are an intentional resource-bound rejection.
The suite verifies pinned actual registrations, exact schemas, seeded upstream
differentials, malformed inputs, RNG independence, real zero-capability guest
execution including failures, manifest/canonical stubs/license, cache hygiene,
and byte-exact pristine-to-V2 patch reconstruction. No hardware-specific path
or credential is required; no frontend extension exists to migrate or test.

Oversize secure-wire strings hit the transport's 1 MiB frame limit before node
execution; this is tested separately from the pack-local text limit. The full
83-case focused gate includes 64 exact seeded comparisons, 13 exact malformed
error comparisons, and a real guest repeating all 64 valid cases plus malformed,
row-limit and wire-limit denials. Global NumPy/Python RNGs remain unchanged.
