# Secure Nodes V2 conversion ledger

Pinned source: `fb38cf3294842d10fe7f0e933595dcd49b008d2b`.

## Exact source census

Upstream registers two backend node IDs and two frontend extensions:

- backend `LoraInfo` → supported;
- backend `ImageFromURL` → security-rejected;
- frontend `LoraInfo` → both execution readouts supported;
- frontend `ImageFromURL` → its widget-set route side effect rejected with
  the node.

Upstream also defines `POST /lora_info`, mutates pack-local `db.json`, queries
CivitAI by a local LoRA's digest, and fetches arbitrary image URLs. There are no
settings, commands, keybindings, startup downloads, or import-time downloads.
The frontend calls `POST /fetch_image`, but upstream defines no such route.

## Working behavior

`LoraInfo` preserves its logical LoRA combo, three string outputs, output-node
status, CivitAI information formatting, first example prompt, Base Model
readout, and multiline information readout. A managed `loras` catalogue entry
is resolved and SHA-256 hashed by the host. The only network authority is the
fixed bounded CivitAI model-version-by-hash integration. The projected record
is cached by content digest in bounded tenant-and-pack-scoped storage, so a
changed file cannot reuse stale metadata.

The frontend uses only `/comfy/api/v2.js`. It adds the two readout widgets with
the published widget collection and updates them from the node's execution
payload. It runs in the opaque `sandbox="allow-scripts"` extension iframe and
has no `document`, `window`, `parent`, or direct `fetch` access.

## Security rejections

- `ImageFromURL` accepts a user-controlled host-side URL and decodes an
  unbounded response. It is an SSRF/private-network and decompression resource
  primitive, not a model-vendor integration. The secure release does not
  register this node or its frontend side effect.
- The `/lora_info` editor-selection prefetch is rejected. Merely selecting a
  combo entry disclosed the local model digest to CivitAI and wrote cache state
  before any queue/execute authority. The same information remains available
  after explicit node execution, including both safe readouts.

Working: 1/2 backend nodes and 1/2 frontend registrations. Rejected: 1/2
backend nodes, 1/2 frontend registrations, and the incidental selection route.
Pending API gaps: none after the bounded CivitAI projection includes
`baseModel` and bounded image metadata.
