# Label property drawing repair

Only `extension-host/host-entry.mjs` changes: `0b3ddfc2` to `bbf1f186`.
The [handoff](handoff/PROPERTY_DRAW_HANDOFF.json) describes the correction and
[patch](host-entry.patch). Label source `63114a2f`, its registry revision,
public declarations, compiled frontend and hydration repair `46882ce0` are unchanged.

Native property handlers intentionally run before writing to support synchronous
replacement/rejection. The old worker bridge copied that intermediate snapshot.
The 20-check diagnostic records six accepted bitmaps containing the prior value.
The shared define/extend helper now queues only worker property notifications
until native settlement finishes. Other hooks keep their existing timing.
Queued notifications are discarded if the node is deleted or its graph/document changes.

The [44-case production regression](evidence/run3/PROPERTY_DRAW_REGRESSION.json)
passes, including five old-source negative controls, define/extend transport,
host/panel/guest updates, replacement/rejection, bound-widget synchronization,
rapid writes, deleted nodes and surface/bitmap cleanup. It executes the production
registry, actual native setter, complete guest, unchanged Label drawing and host
frame acceptance. Canvas/ImageBitmap fixtures record exact drawing commands;
these receipts do not establish browser raster or pointer acceptance.
The finite process exited 0 without OOM in 1.911 seconds: one CPU, 768 MiB
container, 512 MiB Node heap, 90-second ceiling, no network or installs.

[MOE's independent review](INDEPENDENT_SOURCE_REVIEW.json) found no issue in the
source and receipts. MOE did not rerun tests or claim browser acceptance.
Root owns publication and final acceptance; DANNY owns live integration.
Classic and Vue acceptance remains pending in this evidence increment.

All production snapshots, the patch and the three test drivers retain their exact
frozen bytes. [Publication provenance](PUBLICATION_PROVENANCE.json) maps original
and published hashes. Machine paths in controllers and receipts are normalized
to placeholders; the controllers are archived examples requiring explicit local
bindings before replay. They were not rerun after this path-only normalization.
The frozen `handoff/MANIFEST.json` describes original bytes; the
`PUBLISHED_MANIFEST.json` and parent `EVIDENCE_MAP.json` bind the published bytes.
No ZIP, compiler dependency or binary runtime is included.

To reproduce without editing the tested drivers, reconstruct their relative
layout in a new isolated workspace: place this directory at
`coordination/rgthree-storm-20261015/lanes/label/property-draw-r1`; place the bound
TypeScript file at sibling `test-dependencies/typescript.cjs`; populate sibling
`integration-r1/frontend` from `baseline/frontend`, adding `fixtures/errors.ts`
at `src/platform/nodeApi/errors.ts`; copy the workflow to sibling
`integration-r1/handoff-r2/label-acceptance-workflow.json`; copy `fixtures/constants.js`
to workspace `corpus/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/comfyui/constants.js`.
Use a fresh evidence output location rather than replacing recorded runs, bind
existing Node/library locations in the archived controller, and retain its
memory/CPU/time/network/ownership limits. `DEPENDENCY_BINDINGS.json` records the
existing compiler identity. This publication does not execute that replay.

The historical Windows admission record is preserved with an explicit numeric
inconsistency noted in provenance; it is not validation evidence. The independently
admitted Linux diagnostic and successor runs are the passing runtime evidence.
