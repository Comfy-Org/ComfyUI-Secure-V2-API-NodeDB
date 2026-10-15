# rgthree Label repair

The corrected Label source passes its lifecycle regression and is staged for
actual Classic and Vue browser retesting. The new source revision is
`84e4001d5ed8a0525e931dd496288036c89942fc1dd49a43913a18aab0e51bf2`;
its publication status is recorded separately from source qualification.

This change restores the previously empty Label module through public frontend
APIs. It supports text, eight saved formatting properties, drawing, editing and
pinned interaction. Other rgthree repairs remain separate; no whole-pack
completion is claimed.

The first real browser runs loaded the exact R3 assets in both renderers but
found that queued creation events reset saved formatting to defaults. The edit
extension also registered after the node definition, so its hooks were ignored.
Both failures are retained under [lifecycle-r2/browser-failure](lifecycle-r2/browser-failure).
The correction skips creation initialization while graph loading is active,
lets configuration initialize restored state, and registers edit hooks before
the definition. Only `label.js` changes from the previous candidate.

The [correction handoff](lifecycle-r2/handoff/LIFECYCLE_HANDOFF.json) records
34 actual host/guest protocol assertions, including four old-source negative
controls, and 112 focused checks (111 original assertions plus one parse check).
The final bounded process exited successfully in 1.73 seconds. The first test
attempt passed its assertions but timed out because fixture worker intervals
remained active; its receipt remains unchanged. The successor only adds fixture
timer cleanup. These are source/protocol tests, not browser acceptance.

The generic frontend and extension-host prerequisites are unchanged from the
[R3 integration handoff](INTEGRATION_HANDOFF.json). Its full typecheck, 28 actual
Vitest cases, formatting, zero-error lint and production build remain applicable
to those exact files. Lint retains four new architecture warnings and 15 baseline
warnings. The selected source baseline contains 6,781 files and the distribution
manifest binds 1,053 files. No frontend rebuild is required by this pack-only fix.

The [new distribution replay](lifecycle-r2/DISTRIBUTION_REPLAY.json) reconstructs
all 226 V2 files with exact bytes and modes and preserves all 258 original files.
[Registry identity](lifecycle-r2/REGISTRY_IDENTITY.json) and
[complete-source proof](lifecycle-r2/COMPLETE_SOURCE.json) bind all 484 Git files.
The [catalog candidate](lifecycle-r2/CATALOG_STAGE.json) preserves all existing
rows and adds the corrected revision without backend execution or verification
grants. It must be selected together with its matching frontend asset projection.
The old `d9c88479` revision and its registry readback remain historical evidence.

DANNY owns publication and real browser retesting of the unchanged acceptance
workflow. Drawing, nine-field editing, pinned interaction, save/reload and
cleanup must pass in both Classic and Vue. Root owns the corpus source and
registry identity. The existing fixture requires no model or queued render.
The earlier source, build, test and failed-browser receipts remain indexed;
none is relabeled as whole-pack acceptance.
