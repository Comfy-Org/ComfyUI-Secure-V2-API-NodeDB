# Latent Orientation conversion ledger

Upstream: https://github.com/SparknightLLC/ComfyUI-LatentOrientation
Pin: `6134758aba02532e1c1e6226f935d1d129eb24bf` (`x6134758`).

Census: 1 Python registration (`LatentOrient`, display `Orient Latent`) supported;
0 rejected, 0 pending. No frontend extensions, JS-only nodes, routes or host APIs.
Exact legacy inputs, ordered options, unnamed LATENT output and category remain.

`algorithm.py` is byte-identical to the pinned upstream `__init__.py`. The typed
wrapper adds input and projected-output bounds before entering the algorithm.
`SDK_REFS=False`, `SDK_PERMISSIONS=("raw",)`: value-mode raw tensor compute only;
the real outer executor wraps the declared LATENT output. No private constructors,
host imports, filesystem, network, models, storage or graph authority are used.

The returned dict is a shallow copy. Unchanged samples retain identity; centered
crops alias their input tensor storage, rotation retains upstream allocation semantics,
and pad/resize allocate exactly as upstream. Metadata including `noise_mask` is
left unchanged deliberately, even when samples change geometry. Wire transport
does not promise shared host/guest object identity; guest algorithms themselves
preserve those legacy semantics and do not mutate input state.

Resource boundary: strided floating samples, rank 4..6, nonempty dimensions up to
8192, input and projected output at most 16,777,216 elements. NaN/Inf values are
not silently normalized; they retain legacy arithmetic. Higher-rank rotation,
crop and padding retain the literal legacy axes (padding the final two axes).
Non-square higher-rank avg square is rejected, as the legacy interpolation also
fails there. Square higher-rank inputs remain valid no-ops. Bounds exclude larger
requests intentionally without fabricating an output. Device/dtype are unchanged
where the original operation permits. CPU tests do not prove GPU-specific paths.

Persistence disposition: no durable state. All computation uses workflow-owned
orientation and LATENT input; there are no editable files, endpoints, caches,
process counters or preferences. Fresh pack filesystem and fresh guest renders
are tested for the same-input continuity and different-input isolation. No KV
service or durable backing-store claim is needed.

Provenance: upstream pyproject declares `license={file="LICENSE.txt"}` but that
file is absent from the pinned repository. No license is invented or inferred;
the V2 pyproject omits the broken declaration and this boundary remains explicit.

Verification: native-loader census and schema parity, all-mode exact tensor
differentials, odd/even geometry, ranks, dtype/batch/noncontiguous cases, view and
metadata behavior, pre-compute bounds, real isolated guest/raw denial/outer LATENT
typing, fresh-render continuity, canonical stubs, manifest, cache hygiene and
byte-exact pristine-to-V2 patch roundtrip. No shared API or dependency gap.
