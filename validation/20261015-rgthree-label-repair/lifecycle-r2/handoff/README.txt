Label workflow-load repair: source regression PASS; browser retest pending.

Only pack/web/comfyui/label.js changes from the frozen R3 overlay. It defers initialization during graph loading to onConfigured and registers the edit extension before defining the node. No host/frontend/drawing/declaration change or frontend rebuild is needed for this delta.

The bounded terminal run passed34 new production-protocol assertions, including4 expected failures of the old source, and the existing112 focused checks (111 original assertions plus1 source parse). Run2 exited0 in1.73seconds,1CPU,512MiB heap,90-second ceiling. The historical run1 assertions passed but its process timed out124 because complete guest bootstrap timers remained live; run2 adds only explicit fixture-worker teardown. Browser rendering, editing and reload acceptance remain DANNY-owned and pending for this successor.

PACK_SOURCE_BINDINGS.json binds all3 pack files and unchanged R3 prerequisites. label-lifecycle.patch applies at the V2 pack root. LIFECYCLE_HANDOFF.json contains the diagnosis, proof boundaries, historical failure hashes and exact browser retest checklist. Both original browser failure capsules remain preserved in the lane; only filtered report extracts are included here. Root owns registry identity and publication.
