# DaisyChain Text — Secure Nodes V2

Upstream: https://github.com/mittimi/ComfyUI_mittimiDaisyChainText
Pinned commit: `94ba20fda8dc35cd5adfe3fb01715d55149b0bf4` (`x94ba20f`).

Actual registration import: **1 Python node supported; 0 rejected; 0 pending**.
There are **0 frontend extensions, 0 JS-only nodes, and 0 routes**. Upstream's
`WEB_DIRECTORY = './js'` names an absent directory and does not create a frontend
feature. The unused ambient `comfy.sd` import is removed, not bridged.

Node IDs, display/category, required and optional sockets, multiline flag,
output name/type/order, and default method arguments are preserved. Execution
is precisely `text_that_comes_first + text + text_that_comes_last`: no stripping,
coercion, separator, parsing, or escaping. Native malformed-input addition
errors and bounded out-of-schema sequence addition are retained. Input text
is bounded to 64 KiB UTF-8 per socket (surrogatepass for direct calls); unusual
sequence inputs are bounded to 4096 items each. Three accepted text inputs give
an output bound of 192 KiB. Bytes are not supported by the public guest wire.

Authority: public scalar value mode, `SDK_REFS=False`, no permissions, no raw
compute, host imports, network, files, browser globals, or shared API changes.
GPL-3.0 LICENSE is retained byte-for-byte; no license is invented.

Persistence disposition: **no durable pack state**. Inputs are workflow-owned
and travel through normal graph serialization; the pack has no settings, cache,
editable library, globals, or source-adjacent data to migrate. Tests execute the
same inputs in independent real guests after recreating the pack filesystem,
and interleave other graph/user inputs to establish absence of pack state.
This does not claim a cloud storage backend or test the browser serializer.

Evidence: pristine algorithm differentials, exact schema/manifest census,
whitespace/Unicode/adversarial text, defaults, native malformed errors,
deterministic generated cases, input/sequence bounds, independent instances,
real zero-capability guest execution from two fresh roots, pristine integrity,
canonical contract hashes, GPL file preservation, and byte-exact patch roundtrip.
No GPU/model/credential path exists. The focused module has 26 checks; the
combined gate adds 33 shared manifest/patch checks. Across two fresh guest roots,
280 representative/generated results, 16 malformed inputs, and 12 oversized
inputs are checked, plus cross-graph/default/max-size results and wire denial.

Repeatable combined gate (run from this isolated pack-db worktree):

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-mittimi-daisy-chain-text/x94ba20f/ComfyUI_mittimiDaisyChainText-HEAD/v2/tests/test_daisy_chain_text_secure_conversion.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packpatch.py /Users/ben/comfy/ComfyUI_secure_nodes/backend/tests/test_packdb_manifest.py --tb=short
```

All final artifacts must pass this gate twice before completion.
