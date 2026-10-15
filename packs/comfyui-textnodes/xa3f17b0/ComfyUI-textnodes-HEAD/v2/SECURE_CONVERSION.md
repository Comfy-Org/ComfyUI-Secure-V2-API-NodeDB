# ComfyUI TextNodes — Secure Nodes V2

Upstream: https://github.com/akierson/ComfyUI-textnodes
Pin: `a3f17b0926fda30971e38d0f1c0188d9f7d8b3d7`, live HEAD authored 2024-10-20.
Release: `xa3f17b0`. Older active-registry utility, not a claim of new author activity.
The MIT license is retained. Pristine source stays byte-exact.

Actual-loader census: **2 Python supported / 0 rejected / 0 pending** (`Tidy Tags`,
`Prompt Truncate`); **0 frontend extensions / 0 JS-only nodes / 0 routes**.
Exact node IDs, categories, input ordering/defaults/multiline/force-link contract,
and named STRING outputs are retained. Public `io.ComfyNode`, value mode,
zero permissions; no filesystem/network/subprocess/model/raw/DOM authority.

Algorithms remain pack-local:

- Tidy Tags: list-to-string conversion, iterative comma/whitespace cleanup,
  stable exact-case deduplication, and upstream BREAK rewriting.
- Prompt Truncate: comma-separated tag slicing (not tokenizer/BPE counting),
  including zero/negative/oversized counts, whitespace quirks and BREAK rewriting.

Documented compatibility detail: upstream Tidy Tags returns a bare empty string
for falsy/non-string/non-list inputs, an invalid output container. V2 packages
that same intended empty STRING into one valid socket. Non-empty lists passed
directly to Prompt Truncate still raise the upstream `.strip` AttributeError;
invalid slice index types retain their original errors. No silent coercion or
"fix" changes ordinary output. These are prompt formatting tools, not HTML
sanitizers; returned adversarial text stays inert data.

Resource bounds: input text (or comma-joined Tidy Tags list) <=65,536 UTF-8 bytes,
lists <=4096 items, output <=131,072 bytes. Local Python surrogate accounting uses
surrogate-pass encoding. Inputs outside these explicit limits fail closed before
unbounded string work; behavior inside the bounds is differential-tested against
the pin. Only stdlib and the public SDK are required.

Persistence disposition: **no durable pack state**. All editable inputs belong
to workflow serialization. Algorithm-local sets/lists are disposable computation;
there are no endpoints, source-adjacent writes, persistent caches, preferences,
global mutable state, or editable defaults that need cloud user KV. Both nodes
are re-executed in a freshly recreated filesystem/worker to verify continuity.

Focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-textnodes/xa3f17b0/ComfyUI-textnodes-HEAD/v2/tests/test_textnodes_secure_conversion.py --tb=short
```

Tests cover exact census/schema, explicit expected output, deterministic generated
differential inputs, normalization, list/error quirks, bounds, independent calls,
real zero-capability guest executions and fresh-render continuity, manifest,
canonical contracts, MIT provenance, no ambient authority, and byte-exact patch
roundtrip without interpreter-cache contamination. No pending API/dependency/
persistence/hardware/credential boundaries. Shared API/registry untouched.
