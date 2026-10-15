# Text Node With Comments — Secure Nodes V2

Upstream: https://github.com/cdxOo/comfyui-text-node-with-comments
Pin: `aa109023d632974e45455190225ab46e74b29ecc` (live HEAD, authored 2024-08-03).
Release: `xaa10902`. MIT license retained. Registry utility, not a claim of recent author activity.

Census from an actual package import: **1 Python node supported / 0 rejected / 0 pending**;
**0 frontend extensions / 0 JS-only nodes / 0 routes**. Node ID, display name,
category, multiline string default, and single STRING output are unchanged.

The algorithm stays pack-side: remove `//` line comments and non-greedy `/* */`
comments while preserving single/double-quoted strings and escapes. Whitespace,
CRLF behavior, unterminated/nested comment quirks, and non-text TypeErrors follow
the pinned implementation exactly. This is not a language parser or sanitizer:
URLs outside quotes may be stripped, and returned text is not safe HTML by itself.

Public `io.ComfyNode`, value mode (`SDK_REFS=False`), zero permissions. No filesystem,
network, subprocess, host imports, raw tensors, DOM, or runtime installations.
Input and output are bounded to 65,536 UTF-8 bytes (surrogate-pass accounting for
local Python strings). Exceeding this documented resource limit fails closed before
regex work. Within that bound the regex and output are unchanged. Dependencies: stdlib
and the public Comfy SDK only; no model, credentials, or hardware boundary.

Persistence disposition: **no durable pack state**. The source string is a normal
workflow-owned serialized input. All computation is render-local; no endpoint,
file, cache, global mutable state, or editable defaults require user KV storage.
Fresh worker/fresh-filesystem execution is tested and yields identical output.

Focused gate:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-text-node-with-comments/xaa10902/comfyui-text-node-with-comments-HEAD/v2/tests/test_text_comments_secure_conversion.py --tb=short
```

Tests cover exact schemas and actual-loader census, quoted/escaped/adversarial text,
multiline/Unicode/malformed cases, deterministic generated differential inputs,
bounds, real zero-capability isolated guests including a recreated filesystem/worker,
manifest, canonical contract hashes, license, authority, and a byte-exact patch
roundtrip without contaminating pristine source with interpreter caches.

No API/dependency/persistence gaps; no shared API or registry changes in this handoff.
