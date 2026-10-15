# rgthree Label repair

The corrected Label source is registered in the local Docker service as revision
`84e4001d5ed8a0525e931dd496288036c89942fc1dd49a43913a18aab0e51bf2`.
The [independent authenticated readback](registration-r2/READBACK.json) verifies
its complete public registry row and exact source/manifest identity.
Actual browser retesting remains in progress before this PR is merged.

This change restores the empty Label module through public frontend APIs:
text, eight saved formatting properties, drawing, editing and pinned interaction.
Only three V2 pack files change; all258 original files are preserved. The
[official replay](lifecycle-r2/DISTRIBUTION_REPLAY.json) reconstructs all226 V2
files with exact bytes and modes. Other rgthree work is separate; whole-pack
completion is not claimed.

The first real Classic and Vue runs exposed queued creation events resetting
saved settings and extension hooks registered too late. The pack correction
skips initialization while graph loading is active and registers hooks before
the node definition. It passes34 actual protocol checks, including four old-source
negative controls, plus112 retained focused checks. The first fixture timeout
and all earlier browser failures remain unchanged in the evidence tree.

The corrected live source preserves saved properties and opens the nine-field
editor. The real Vue trace confirms all nine edits reach the graph and unpinned
dragging works. It then exposed a generic host defect: textarea/select live
values were not restored from serialized attributes, leaving the displayed
title empty and alignment left after initial rendering and updates.

The [host-only successor](dom-values-r1/handoff/DOM_VALUES_HANDOFF.json) restores
those live values after sanitized children/options have been appended. It changes
only `ui-renderer.mjs`; pack identity and compiled frontend remain unchanged.
It passes26 actual production guest/host DOM checks against jsdom, including two
old-source failures, edit event round trips, repeated updates, empty/escaped/
unmatched values and unchanged unsafe-markup rejection. The bounded process
exited0 without OOM in1.93seconds and its exact owned container was removed.
This source/DOM evidence does not substitute for real Chromium acceptance.

The unchanged R3 prerequisites retain their full typecheck,28 Vitest cases,
formatting, zero-error lint (four new architecture and15 baseline warnings),
production build and1053-file distribution binding. Apply the narrow host
successor to that baseline; do not replace the selected rows frontend.

DANNY owns the final live host deployment and unchanged-workflow Classic/Vue
checks for rendering, editor values, pinned interaction, save/reload and cleanup.
No model or queued render is required. The corpus PR remains draft until those
checks pass; source registration grants neither backend execution nor whole-pack
verification.
