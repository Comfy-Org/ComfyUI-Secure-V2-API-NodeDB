Label drawing update repair: source regression PASS; browser acceptance pending.

Only host-entry.mjs changes:0b3ddfc2 ->bbf1f186. The registry deliberately settles native property callbacks before writing, but the old asynchronous bridge copied its snapshot too early. The accepted worker bitmap therefore retained the prior angle/font/alignment/color. A20-check diagnostic confirmed6 stale accepted frames without restoring graph state.

The successor queues only property-change worker notifications until synchronous settlement finishes, then snapshots actual committed state. All other lifecycle hooks retain their timing. Native setValue/reject and property-bound widget synchronization stay unchanged. Queued notifications are cancelled for removed nodes and changed graph/document scopes.

The44-check successor regression passed5 old-source negative controls plus actual define/extend/native/panel/guest paths, accepted draw-command parity, replacement/rejection, rapid writes, deletion and single-surface lifecycle. It executed the production registry, the actual native LGraphNode.setProperty, complete guest, unchanged Label and host frame acceptance. Exit0,noOOM,1.911s,1CPU,768MiB container,512MiB Node heap,90-second ceiling,offline. Canvas drawing-command fixtures do not claim browser pixel/raster acceptance.

Label63114, registry identity, public API declarations, frontend source and hydration46882 remain unchanged. No frontend compiler rebuild is needed for this one host module delta. Root owns publication; DANNY owns actual Classic/Vue rendering/edit/save-reload acceptance.
