# Substring — Secure Nodes V2 conversion

Source: https://github.com/godspede/ComfyUI_Substring
Pinned commit: `1b1fce10cdfb1be355104d4d072f9194deb3ce6f` (`x1b1fce1`).

Actual entrypoint census: 1 Python supported, 0 rejected, 0 pending;
0 frontend extensions, 0 JS-only nodes, 0 routes. Node ID `SubstringTheory`,
class `SubstringFunction`, display name `Substring`.

The algorithm stays in the pack with `SDK_REFS=False`, no permissions,
and no host imports. Positive lengths select a prefix, negative lengths select
a suffix, and zero returns empty. Literal text `undefined` becomes empty before
slicing; other strings, Unicode code points, whitespace and adversarial markup
are preserved exactly. Output-node semantics include both the STRING result and
the upstream `ui.text` payload. This pack has no custom frontend renderer.

Schema defaults/ordering/multiline/category/output status are preserved. Direct
inputs must be a string and a nonboolean integer; text is bounded to 1 MiB UTF-8.
Malformed/oversize direct inputs intentionally fail closed. Slicing preserves
Python's out-of-range/negative-index behavior. No filesystem, network, raw
tensor, model, route or global mutation capability is requested. The unused
legacy `os` import is removed. No new shared API is needed.

The upstream pyproject declares a LICENSE file but the pinned upstream tree
contains no license text. The conversion retains that upstream declaration and
does not invent a license. This is a packaging/licensing metadata caveat.

Validation covers differential prefix/suffix/sentinel/Unicode/UI cases, bounded
malformed input, real isolated zero-capability guest execution, capability
denial for attempted raw-tensor substitution, exact registration/schema,
canonical SDK hashes, pristine identity,
cache hygiene, manifest and byte-exact pristine-to-V2 patch reconstruction.

Focused command from the isolated pack-db worktree:
`PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-substring/x1b1fce1/ComfyUI_Substring-HEAD/v2/tests/test_substring_secure_conversion.py`

The 101-test gate includes 88 explicit differential cases, 1,000 seeded
randomized comparisons, 40 real guest scalar/UI cases, raw-tensor substitution
denial and UTF-8 byte-limit checks. There are no model/hardware/credential paths
in this pack; no behavior is deferred for those reasons.
