# Secure conversion evidence

## Source pin and census

- Upstream: `https://github.com/ethanfel/Comfyui-Workflow-Snapshot-Manager`
- Commit: `ff59e58b335866ebc203ad4c506633531f091709`
- Python census: one node, `SaveSnapshot`
- Frontend census: one logical extension, `ComfyUI.SnapshotManager`
- Legacy server surface: fifteen private HTTP routes, replaced rather than
  bridged
- Canonical composite API: pack-db commit
  `1b080d6edd93d670399a169279b1e61e8d2bf247`

Upstream contains two mutually exclusive `app.registerExtension()` calls for
modern and legacy ComfyUI versions. They represent one extension, not two
frontend features.

## Authority mapping

| Legacy authority | Secure V2 replacement |
|---|---|
| private filesystem snapshot/profile routes | `comfy.storage`, scoped by host to user and pack |
| `app.graph.serialize()` | `comfy.workflow.snapshot()` |
| graph replacement / open-copy | `comfy.workflow.open()` with typed replace/new modes |
| document/global DOM | mounted sidebar/dialog containers and `ownerDocument` |
| global keydown listener | host commands scoped to `canvas` |
| direct JSON download/upload DOM | `comfy.files.download()` / `comfy.files.pick()` |
| graph-change hooks on host internals | documented `comfy.graph.version` polling |

The frontend has no manifest permissions. Storage, workflow, files, commands,
and mounted UI are closed, typed host services. Python declares only `raw` and
`ui`, used respectively to reproduce the optional JPEG thumbnail when an
`AnyType` value is actually an image ref and to deliver the capture request.

## Bounds and rejection behavior

- 200 records maximum in an index/import
- 6 MiB maximum serialized graph/record
- 32 chunks maximum, each safely below the host's 1 MiB value limit
- 50 workflows maximum in a profile
- 64-character storage IDs, 500-character labels, and 50,000-character notes
- malformed records, cross-workflow records, unsafe IDs, incomplete chunks,
  and over-limit data fail closed
- partial writes are deleted before an index can publish them
- locked snapshots survive automatic pruning and bulk clearing

## Migration

Legacy filesystem/IndexedDB migration is outside an isolated pack's authority.
The supported migration path is explicit JSON export/import.

## Verification

The focused gate covers:

- exact pristine and secure node/extension census;
- Python schema, validation, passthrough behavior, and UI capture request;
- frontend auto/manual/node capture, replacement restore, multi-tab profile
  restore, diff/import/export wiring, mounted UI, and canvas-scoped commands in
  a realm without browser globals;
- chunk limits, quota failures, malformed records, pruning, locked records,
  workflow boundaries, and simulated tenant isolation;
- canonical API declaration pin and fresh generated manifest;
- pristine-to-V2 patch round trip and cache cleanliness.
