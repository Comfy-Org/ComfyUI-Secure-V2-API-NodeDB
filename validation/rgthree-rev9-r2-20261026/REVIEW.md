# Independent rgthree rev9 R2 review — 2026-10-26

**CLEAR_FOR_SOURCE_PUBLICATION. No blockers found.** Audit V3 is repaired without adding pack-specific public API. This verdict covers the sealed source stage and canonical artifacts; existing browser, runtime, registry and deployment holds remain.

Reviewed `coordination/rgthree-rev9-r2-20261026/` against corpus `e18b3c87c947fbabb33ae0fae1cbce7c494aceb1` and frozen `coordination/rgthree-rev9-20261022/`. Final `HANDOFF.json` SHA256 is `ba7d1980bb374a3811d605b25e26bee09bb63126afa4bf221b87b27a78af1471`; `STAGE_MANIFEST.json` is `da35d9e8453e37cdb8ce82cd3be88f02dad142f7bfd0834639b1bea0a8d90bb4`.

Only three of 221 v2 files differ from the rejected draft:

- `comfy-api.d.ts` exactly matches main: SHA256 `53c296aa7e1f3454ecbf02980a2f3d532d79f7f5e99eda311de689ff56447ded`, with the 12 unpublished declaration lines removed.
- `connection_layout.js` removes the `collapsedKey` helper and the entire collapsed-position read/write/cache block, plus updates its scope comment. Expanded position math, direction overrides, all 24 IDs, labels, grouping, colours, menus, serialization and stabilization wiring are unchanged. Its SHA256 is `a8053afa660b89adc9bdda293851ab26a8bea6fe3e1c04ea29abb7d632b8dd35`.
- `SECURE_CONVERSION.md` records the repair and missing purpose. All other **218 v2 files**, including Reroute and the revision 4–8 fixes, retain the draft's exact bytes. No new shim or API is included. Audit V1/V2 remain with their frontend/host owners.

The retained finite evidence is consistent with the actual stage: 46/46 original-comparison cases, 63/63 regression checks, ring PASS, 45/45 adapted rev9 checks and API-member PASS. Module hashes match. The syntax receipt's exact file set equals the **74** served JS files; the corrected documentation and handoff no longer assume 123. These are module/fake-host results, not browser or scientific qualification.

The rejected-draft controls discriminate the repair. The same harness runs all 768 type/layout/grouping cases through six passes; R2 sends no unpublished patches and settles after the first pass. The frozen draft emits four unpublished fields per case. A strict snapshot Proxy rejects the draft's `collapsedPosition in snapshot` read, and patch keys are checked against the pinned published `SlotPatch`. The API checker also rejects the draft's unpinned d.ts. The other copied suites/helpers are unchanged; Reroute fallback, threshold and older regression controls remain. Historical draft guest/mutant results are explicitly excluded from R2 acceptance.

All 223 stage hash/size pins match, with exact membership, no deletions and no mode changes. Linux stage bytes/modes agree with the manifest and main's Git modes; the added module is 0644. All 480 baseline Git blobs match the reviewed data, including 258 pristine files. All current packet checksums, handoff artifact/helper pins and the frozen draft's 276 checksum pins match.

Own stdlib JSON/difflib calculations over verified Git/pristine and stage data reproduce both main's existing pair and R2's new pair byte for byte, without importing or running the supplied generator. The deterministic derived ZIP also matches exactly:

| Artifact | SHA256 |
| --- | --- |
| Canonical JSON | `c9f119cb2f8029788889981351cd0b6591927bf8dd6192137731519b2ae3df07` |
| Canonical diff | `5ba2315d8ec9413dc48d62c2d713627927e54e7fa2880c83d1c94ea93aace47c` |
| Derived ZIP, 320,711 bytes | `873f85164ed73aed98d1257d2a7f2a5e9a108f8fc1412f833104fd16c591becf` |

The retained single metadata build/replay pins the exact `268df53f…` tool, reproduces main before building, and reports pair/ZIP replay plus old-pair and tampered-pristine refusals. Those controls compare a wrong materialized tree and reject a changed pristine base before writing v2. The ZIP contains only the exact pair at fixed timestamps/mode 0644 and remains outside the stage. Pair counts remain copy 140, convert 67, add 14, delete 51. The mode-sensitive v2 digest independently matches `5439d4946d62229ff35ed6b79ce3cad335375afbb895d4fd2836d0bfe629e126`.

Notes, not publication blockers:

- Whole-node collapsed title-edge socket geometry remains **PARTIAL for all 24 F01 types**. Expanded grouping remains implemented. Reroute still lacks F05 insertion, F06 per-link colour and F17 connection policy; its existing geometry/zoom fallback remains. The docs disclose these purposes without treating a live unapproved field as API.
- Dispositions remain **6/40 tested, scoped**; no node gains acceptance from these finite checks. R2 browser/real-runtime qualification and later registry/deployment work remain open. A future general facility requires MIKE's publication; a critical-pack shim requires its separate review.

Only source/data reads, Git object inspection and own stdlib AST/hash/ZIP/JSON/diff calculations were performed. No supplied script, test, checker, generator, replay function, SDK/scientific import, browser or service was executed by this reviewer. Candidate and corpus were not changed; nothing was published or deployed. Detailed checks are in `evidence.json` and `frozen-and-links.json`.
