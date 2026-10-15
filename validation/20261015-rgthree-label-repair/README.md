# rgthree Label repair

The corrected Label source is registered in the local Docker service as revision
`84e4001d5ed8a0525e931dd496288036c89942fc1dd49a43913a18aab0e51bf2`.
The [independent authenticated readback](registration-r2/READBACK.json) verifies
its complete public registry row and exact source/manifest identity.
Classic browser acceptance now passes. Vue acceptance remains pending its
confirmed focused-field replacement repair before this PR is merged.

This change restores the empty Label module through public frontend APIs:
text, eight saved formatting properties, drawing, editing and pinned interaction.
Only three V2 pack files change; all 258 original files are preserved. The
[official replay](lifecycle-r2/DISTRIBUTION_REPLAY.json) reconstructs all 226 V2
files with exact bytes and modes. Other rgthree work is separate; whole-pack
completion is not claimed.

The first real Classic and Vue runs exposed queued creation events resetting
saved settings and extension hooks registered too late. The pack correction
skips initialization while graph loading is active and registers hooks before
the node definition. It passes 34 actual protocol checks, including four old-source
negative controls, plus 112 retained focused checks. The first fixture timeout
and earlier browser failures remain unchanged in the evidence tree.

The corrected live source preserves saved properties and opens the nine-field
editor. The recorded Vue trace confirms all nine edits reach the graph and
unpinned dragging works. It exposed a generic host defect: textarea/select live
values were not restored from serialized attributes. The
[DOM hydration repair](dom-values-r1/handoff/DOM_VALUES_HANDOFF.json) restores
those values after sanitized children/options have been appended. It changes
only `ui-renderer.mjs` and passes 26 production guest/host checks against jsdom,
including two old-source failures, repeated updates, native control-value
semantics and unchanged unsafe-markup rejection.

The latest [property drawing repair](property-draw-r1/handoff/PROPERTY_DRAW_HANDOFF.json)
fixes a separate host timing defect. Native handlers run before property writes
to support synchronous replacement/rejection; the old bridge copied that
intermediate snapshot, so Label could draw the previous value. A 20-check
production diagnostic confirmed six stale accepted frames. The shared define/extend
bridge now queues only worker property notifications until native settlement
finishes, then snapshots committed state. Other hook timing and native
replacement/rejection behavior remain unchanged.

The [44-case successor regression](property-draw-r1/evidence/run3/PROPERTY_DRAW_REGRESSION.json)
passes, including five old-source negative controls, host/panel/guest updates,
replacement/rejection, bound-widget synchronization, rapid writes and cleanup.
It exercises the production registry, actual native setter, complete guest,
unchanged Label and host frame acceptance. The bounded process exited 0 without
OOM in 1.911 seconds. Drawing-command/ImageBitmap fixtures verify accepted frame
contents; real Chromium raster and pointer behavior remain the final gate.
[MOE's independent source review](property-draw-r1/INDEPENDENT_SOURCE_REVIEW.json)
found no issue and did not rerun tests or claim browser acceptance.

The unchanged R3 prerequisites retain their full typecheck, 28 Vitest cases,
formatting, zero-error lint (four new architecture and 15 baseline warnings),
production build and 1053-file distribution binding. Both narrow host fixes
preserve Label `63114a2f`, the registered pack revision and current compiled
frontend. Apply the host asset overlays while retaining the selected rows,
login and pack-loading assets; this increment requires no frontend rebuild.

MERVYN owns publication and browser acceptance; JERRY owns live integration.
Classic and Vue checks must verify visible drawing after the final edit,
editor values, pinned interaction, save/reload and cleanup. No model or queued
render is required. The PR remains draft until those checks pass; registration
grants neither backend execution nor whole-pack verification. The earlier README
and evidence index are preserved under `historical/pre-property-draw-r1`.

The [actual browser window](browser-window1/ACCEPTANCE.json) records 43 passing
Classic interaction checks and reviewed screenshots, including all nine live
editor values, drawing, pin/unpin, save/reload, pan/zoom and cleanup. The first
Classic overlap failure and Vue focused-field edit loss remain visible in the
record. Vue is not qualified: repeated unchanged-markup updates replace focused
controls during typing. Its isolated generic host repair is pending.
