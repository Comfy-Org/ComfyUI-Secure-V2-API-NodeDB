# Secure Nodes V2 conversion ledger

Pinned upstream: `9e0a6e700299182fc05c58b62e7ad9f72182a78b`

## Exact census and disposition

- Backend: 1/1 supported — `WD14Tagger|pysssss` (`WD14 Tagger 🐍`).
- Frontend: 1/1 extension supported — `pysssss.Wd14Tagger`.
- Frontend intent 1/3: download/status indication is supplied by declared,
  host-owned model provisioning and progress instead of a global prototype
  monkey-patch and private event channel.
- Frontend intent 2/3: per-batch execution tag readouts use disabled,
  non-serialized V2 text widgets and refresh without stacking stale widgets.
- Frontend intent 3/3: quick image interrogation creates and connects a normal
  visible WD14 node, partially queues it, and presents the result in a safe V2
  dialog. It does not turn a renderer URL into a private HTTP or filesystem
  request.
- Rejected nodes/intents: none.

## Security and behavior boundary

The pack declares eleven public Hugging Face `model.onnx` weight files at
immutable revisions with exact SHA-256 values. They are on-demand and cached
by the host; a warm guest also avoids a repeated broker lookup. The three
immutable label CSV generations are vendored pack data with revision and hash
provenance.

The generic host facility was also validated centrally with the real default
public model: the pinned 326,197,340-byte `wd-v1-4-moat-tagger-v2` artifact was
downloaded once, structurally validated, loaded by ONNX Runtime, run against a
real IMAGE, and produced a `(1, 9083)` opaque score matrix whose sparse paging
returned ordered strict-threshold indices. A second run reused the installed
file and model-session cache instead of downloading again.

Core owns only closed ONNX image preprocessing/inference and an opaque,
bounded classifier score matrix. The pack owns WD14 categories, label lookup,
thresholds, strict comparison, exclusions, character-before-general ordering,
underscore replacement, parenthesis escaping, and prompt formatting. No WD14
policy or algorithm was moved into core.

The active frontend module imports only `/comfy/api/v2.js` and is exercised in
an iframe-shaped realm without `window`, `parent`, `top`, legacy globals, or
ambient network APIs. The copied legacy `web/` sibling is retained solely for
a complete patchable tree; `WEB_DIRECTORY = "./js"` makes it inactive.
