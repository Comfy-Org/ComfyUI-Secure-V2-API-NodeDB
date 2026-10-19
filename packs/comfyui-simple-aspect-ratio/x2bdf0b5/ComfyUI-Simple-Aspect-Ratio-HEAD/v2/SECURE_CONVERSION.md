# Simple Aspect Ratio conversion

Upstream: https://github.com/wwwins/ComfyUI-Simple-Aspect-Ratio at
`2bdf0b5b8f86d09366536dd5437dae79e1e01a99`. All five original Git files
and the MIT copyright/license are retained. One original node,
`SimpleAspectRatio`, is converted with its original calculation module
byte-identical. ID, display name, category, input names, eleven aspect ratios,
two orientations, named integer outputs and native errors are preserved.

The wrapper uses the existing public `ComfyExtension`, `io.ComfyNode`,
`io.Schema`, `io.Combo`, `io.Int` and `io.NodeOutput` APIs. It has
`SDK_REFS=False`, empty permissions and no models, assets, routes, frontend or
private dependencies. It does not need the TinyTerra/Light URL SDK repairs.

Validation on 2026-10-19: all 30 original-versus-actual-SDK cases passed
(22 UI combinations, two additional successful direct calls, six exact
exceptions), including schema, single registration, explicit extension and
NodeOutput checks. These ran in the recorded Mac development environment;
they do not imply general managed-runtime adoption. Normal manifest generation,
canonical JSON/diff generation and independent pair/ZIP replays passed.

The local PC Docker Node Pack Repository TEST service also executed the
unchanged production node through gVisor. A TEST-only typed consumer asserted
the two original width/height results and rendered 1024x576 and 512x768 PNGs.
A deliberate wrong expected width failed with the exact expected AssertionError.
The test helper and its extra manifest entry are not part of this release.
Failed transport/fixture/declaration attempts remain in the validation record.

Current receipts, exact scope and artifact hashes are under
`validation/20261019-simple-aspect-ratio/` in the corpus. The public node
manifest and every executable byte match the tested candidate; only this
documentation was updated after the run and its canonical pair was regenerated
and replayed. Normal catalogue registration and active installation are tracked
separately and are not implied by the TEST session.
