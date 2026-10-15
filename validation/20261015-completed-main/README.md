# Completed conversion publication, 2026-10-15

This import brings 67 previously committed, historically validated conversions
from `codex/oct8-conversion-set` onto `main`. The catalogue increases from 171
to 238 entries. One pre-existing uncatalogued V2 folder remains, giving 239
distinct V2 pack folders. These inventory totals are not a new claim that every
node in every historical pack has passed current Cloud testing.

## Selection

| Historical evidence | Packs |
| --- | ---: |
| Explicit coordinator whole-pack acceptance in the October 8 ledger | 42 |
| Earlier verified registration commits, conversion reports and tests | 25 |
| Total imported | 67 |

`SELECTION.json` identifies each pack, original upstream commit, preserved
original/V2 directories, exact patch files, historical evidence and limits.
`HISTORICAL_ACCEPTANCE_LEDGER.json` preserves the existing October 8 ledger;
its historical local paths are provenance references, not current test outputs.

The source commit is `0c4e2d8e7040ff2f18ee1c61aadcf2f943d628af`.
The receiving main commit is `e2b6c3e34558c9929f0eee2baa02852d2a1de9fa`.
All imported Git blobs and file modes match the source commit. Existing main
pack trees, the three recent accepted conversions, and validation records are
preserved. Derived patch ZIP files are omitted; the JSON/diff pair is committed.

## Validation performed for publication

The official `comfy_secure_nodes.packpatch` tool rebuilt all 67 V2 trees from
their pristine originals and checked-in patch pairs. Every replay passed exact
bytes and file modes, and every pristine source file remained unchanged.
`DISTRIBUTION_REPLAY.json` records tool identity, artifact hashes and results.
No pack implementation was imported or executed during these artifact checks.
Historical runtime evidence retains its original platform and workload limits.
Vendored whitespace and license/provenance notices are preserved verbatim.

All four current workers separately reported no completed whole pack awaiting
publication; see `WORKER_COMPLETENESS_CHECK.json`. Their large-pack candidates
remain unfinished, and are not added to this batch.

## Outstanding reconciliation

Five branch-only packs are still being reviewed for completion evidence:
`comfy-join-prompt`, `comfyui-kmcdev-image-filter-adjustments`,
`comfyui-mosaic-blur`, `comfyui-propost`, and `comfyui_resolution-and-ratio`.
The October 8 ledger did not include them in its coordinator acceptance count.
That omission alone does not prove they are incomplete; their individual
dispositions must be checked before making that claim.

The existing rgthree Label stub is documented separately under
`validation/20261015-rgthree-label/`. Its repair remains open.
