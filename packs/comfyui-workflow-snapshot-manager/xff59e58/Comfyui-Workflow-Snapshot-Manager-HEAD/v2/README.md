# Workflow Snapshot Manager — Secure Nodes V2

This is the Secure Nodes V2 conversion of Workflow Snapshot Manager, pinned to
upstream commit `ff59e58b335866ebc203ad4c506633531f091709`.

It keeps workflow history inside the host's pack- and user-scoped storage and
uses only the typed V2 frontend API. No private backend routes, ambient browser
storage, global keyboard listener, raw network access, or host DOM access are
used.

## Supported behavior

- automatic capture of meaningful graph changes, with debounce and a minimum
  interval;
- manual capture from the action bar or canvas-scoped Ctrl/Cmd+S command;
- node-triggered capture through the `SaveSnapshot` passthrough node;
- a mounted sidebar for browsing, locking, deleting, exporting, importing,
  diffing, and restoring snapshots;
- a verified return-point snapshot before replacement restore;
- bounded per-workflow retention, locked-snapshot preservation, age pruning,
  and an overall 6 MiB record limit;
- exact-snapshot profiles that reopen their workflows as separate tabs.

The storage format is chunked beneath the host's 1 MiB per-value limit. The
host supplies tenant and pack isolation; storage keys expose neither filesystem
paths nor another tenant's data.

## Deliberate secure-mode differences

- Legacy snapshots in the extension's private server directory or IndexedDB
  cannot be read by an isolated pack. Export them from the legacy extension and
  import the JSON through the secure sidebar.
- Restoring one snapshot replaces the active workflow; loading a profile uses
  the generalized typed `mode: "new"` workflow operation for each pinned state.
- When the passthrough value is an image ref, the node uses its declared `raw`
  capability to preserve the legacy bounded JPEG thumbnail. Its declared `ui`
  result carries the capture request to the mounted extension.

See [SECURE_CONVERSION.md](SECURE_CONVERSION.md) for the census, authority
mapping, limits, and verification evidence.
