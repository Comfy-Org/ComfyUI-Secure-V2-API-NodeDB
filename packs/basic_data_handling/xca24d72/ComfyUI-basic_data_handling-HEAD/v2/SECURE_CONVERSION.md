# Secure Nodes V2 conversion

Pinned upstream: `StableLlama/ComfyUI-basic_data_handling` at
`ca24d72ccc26f435c519f70ed787ee6aeb3f0666` (tree
`befaa5ebf984cc6c1109be16f93c1fb8647bcad8`, release `xca24d72`).

The pinned pack registers 309 backend nodes and one frontend extension.
This conversion supports 289 backend nodes and the dynamic-input extension.
Twenty path nodes refuse execution because their defining behavior reads or
writes arbitrary host paths, reveals process directories/environment values,
or enumerates ambient files. Ten lexical path operations remain supported;
they manipulate strings only and never touch the filesystem.

All ordinary Boolean, numeric, string, regex, collection, math, time and
tensor algorithms remain pack-side. Python values that JSON cannot represent
(`set`, bytes, datetimes, timedeltas, and dictionaries with non-string keys)
use a private tagged representation while crossing the host and are restored
before the next Basic Data Handling node runs. Tensor operations use only the
published `raw` tensor capability. Lazy branch nodes use `graph.block` rather
than importing ComfyUI's execution objects.

The frontend uses the opaque V2 node facade to preserve grouped dynamic
inputs, the single trailing empty row, widget-backed wildcard inputs, and
load/configure restoration. It has no DOM, graph-global, route, filesystem,
or network authority.

Backend: 289 supported, 20 security-rejected, 0 pending.
Frontend: one supported registration, 0 rejected, 0 pending. The transformed
pack-side algorithms pass the pinned upstream
suite outside the deliberately excluded ambient-path tests and its optional
test-only `frozendict` dependency (261 tests), plus conversion-specific
dictionary, path, tensor, transport, real-guest, and production-iframe
coverage.

This release is sealed against the published V2 contracts:

- Python: `8800a3ac91604c8b67185bcac307a202d644ed253c2f6ffe66251a32a3cfa9c9`
- TypeScript: `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`
