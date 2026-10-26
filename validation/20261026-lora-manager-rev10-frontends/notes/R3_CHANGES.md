# LoRA Manager rev 10 r3: saved-layout repair for Create Hook, Text and WanVideo (review LORA10-B1)

- **Review:** Root `coordination/review-lora-rev10-20261026/` (REVIEW.md, findings.json). Verdict
  CHANGES_REQUIRED_FOR_R4A_ACTIVATION, blocker B1 only.
- **Base:** r2, frozen and untouched at `coordination/lora-rev10-frontends-20261021/` (SHA256SUMS `f7235841…`).
- **Corpus:** main `e18b3c87`. The LoRA subtree is unchanged since r2's base `a45522ff`.
- **This package:** a new, separately sealed folder. Nothing is published, deployed or committed.

## B1 and what r3 changes

**The finding.** The shared widget types activate three nodes whose original saves are metadata-first, as established
by source. The original's `createAutocompleteTextWidgetFactory` adds a hidden `__lm_autocomplete_meta_text` widget
immediately before every autocomplete text widget (`web/comfyui/vue-widgets/lora-manager-widgets.js` 16723-16758,
16852-16860).

| Node | Original save | r3 restore (`onConfigured`) | Where |
|---|---|---|---|
| Create Hook LoRA | `[meta, text, rows]` | the native `loadedGraphNode` merge (`create_hook_lora.js` 117-135), fed by the saved text and rows: rows = `mergeLoras(text, savedRows)` written once, then the text | `create_hook_lora.js` (`configure`), detection `originalAutocompleteLayout` |
| Text (LoraManager) | `[meta, text]` | the saved text by name (the original Text has no `loadedGraphNode`) | `saved_layout_restore.js` |
| WanVideo Lora Select | `[low_mem_load, merge_loras, meta, text, rows]` | the two BOOLEANs, which core already places correctly, are not touched; the native merge (`wanvideo_lora_select.js` 117-132) restores the text and rows | `saved_layout_restore.js`, detection `originalWanLayout` |

**What else applies to these nodes.**
- **Non-original saves.** Older and converted saves (`[text, rows]`, `[text]`, `[low_mem_load, merge_loras, text,
  rows]`) are not migrated. For Hook and Wan the native load merge still runs on them, as in the original; it writes
  only if the rows differ.
- **Malformed values.** Anything that is not a string text and a row array is left as placed, and the text widget
  refuses it visibly.
- **Live.** All three are inert on live c6b97a15. Their text/loras inputs are sockets there, so there are no widget
  handles to restore. Wan's two BOOLEAN widgets are untouched.
- **Load only.** Edit-time behaviour stays held: Wan's text <-> rows sync and autocomplete.

**Hook's own listeners.**
- **The `onConfigured` caller:** `builder.onConfigured((node, data) => states.get(keyOf(node))?.configure(data))`.
- **`configure(data)`.** It cancels a pending debounce first, so a placement-time row change can't rewrite the restored
  text 80 ms later. It also sets the echo guards (`ownRows`, `ownText`) before writing.
- **Shape guards.** The text listener now ignores non-string values and the rows listener non-array values. Only a
  shifted placement produces those. The review notes the listeners met "invalid shapes"; with asynchronous delivery the
  old listener wrote `[]` over the placed rows before the migration ran (the guard mutant shows it).
- **The helper.** The exposed `restore(node, savedValue)` is unchanged.

**What stays as in r2.**
- `text_row_sync.js` and `prompt_inputs.js` are byte-identical to r2, so Loader, Stacker and Prompt order and behaviour
  are unchanged.
- `FRONTENDS` gains `savedLayouts`, appended last, so the existing order is unchanged.
- No public API, `.d.ts`/`.pyi`, manifest or schema change. All current holds stay (review LORA10-N4).

## Files (candidate/secure_web, vs r2)

| File | r3 | sha256 |
|---|---|---|
| `create_hook_lora.js` | edited: `onConfigured` → `configure`, shape guards | `b383a657519780adeaeb4b87a30e919110013c1d273f42321602b89f022961ef` |
| `lm_frontends.js` | edited: registers `savedLayouts` (appended); header | `839f19bf582f97a87133e5810cab920c67c7b6c9a66125203d7aae11da518a59` |
| `original_layout.js` | edited: `originalWanLayout`; header (all metadata-first layouts) | `4fb9c8cf0490e5df27274aa28cc344939f2758d18254661d0a033cad61ec1d55` |
| `saved_layout_restore.js` | new: Text and Wan restore | `a8dbca601eda41151f56b7f84871e12b8a47b753e6a69d8cf5c037cc2126bd2d` |
| the other 7 | unchanged from r2 | see `assembled/ASSEMBLY_MANIFEST.tsv` |

- `diffs/r3-vs-r2/` holds the r3 changes; `diffs/vs-main/` holds every candidate file against main.
- `assembled/secure_web/` is the 47-file tree: main's 41 plus 6 new (`assembled/package.json` is only the node ES-module
  marker).

## Tests

- **How it was run.** `tools/run_rev10_tests_r3.sh` uses the same command and permission model as r1/r2: node v25.9.0
  `--permission`, no `--allow-net`, no child processes, reads only inside this package, writes only under `results/`.
  Exact commands are in `results/**/RUN_COMMAND.txt`.
- **Result: 60/60 passed.** The report `results/REV10_UNIT_TESTS.json` has sha256
  `a858eadbf3570c98ddc8a0ac9bfe5e9fc95599d27001df59a372ebc1b2f743f4`; the repro run was identical. It covers r2's 44
  (the E1–E3 expectations now include `savedLayouts` and its two `extend` calls) plus 16 new:

| ID | Case |
|---|---|
| H1 sync/async | Hook, original layout (positive). Before: shifted. After: text restored, rows = the native merge of the saved rows, each widget written once, active names from the saved rows. Re-save `[text, rows]`; reloading it writes nothing |
| H2 sync/async | Hook, older/converted `[text, rows]` (negative for the migration): the text is never written, and the native merge writes once |
| H3 sync/async | Hook near misses (metadata version 2, extra key, two values, rows not an array): no writes, refused visibly |
| X1 sync/async | Text, original layout (positive): restored by name, written once, re-save idempotent |
| X2 | Text: the converted `[text]` and near misses are left untouched |
| V1 sync/async | Wan, original layout (positive): BOOLEANs placed and never written; text and rows restored once; re-save `[b, b, text, rows]` idempotent |
| V2 sync/async | Wan, converted `[b, b, text, rows]` (negative): not migrated; the native merge writes once |
| V3 | the real Wan example (`wanvideo_1_3B_control_lora_example_01.json` node 107, an older original before `merge_loras`): not matched, left as placed (below) |
| V4 | Wan near misses (string prefix, metadata version 2, rows not an array): no writes |
| L10 | live: Hook, Text and Wan loads are inert; Hook's `prev_hooks` socket is still added |

- **Fixtures.** The pack's examples contain no current-format save of Hook, Text or Wan. H1, X1, V1 and the near misses
  therefore use the source-proven layouts filled with real saved values, disclosed as derived (like r2's M3):
  - Basic Loader node 56's text and rows;
  - Basic Prompt 78's text;
  - Wan example node 107's text and rows.
- **The Wan example** is copied as data with its blob (`ed4d8adb`) and sha256 (`14ffb5c5…`) in
  `tests/fixtures/example_workflows/FIXTURES.tsv`. The runner refuses to report if any fixture's hash differs.
- **Mutants** (`results/MUTANTS.txt`): all six fail exactly the expected tests.
  - r2's three, unchanged:
    - echo order → R2.sync;
    - Loader/Prompt migration disabled → M1–M3 in both modes;
    - migration after the re-merge → M1.sync, M3.sync and M3.async.
  - r3's three:
    - Hook's `onConfigured` unhooked → H1.sync, H1.async and H2.sync;
    - Hook shape guards removed → H1.async and H3.async (the intermediate `[]` write);
    - Text/Wan migration disabled → X1 and V1 in both modes.

## Recorded, not repaired

- **Pre-`merge_loras` WanVideo saves** (V3). The real example is `[low_mem_load, text, rows]`. Core places it by
  position: `merge_loras` gets the text string, and on r4a `text` gets the rows. This predates rev 10: on live the
  BOOLEANs are the only widgets, and `merge_loras` gets the text in the same way. It isn't B1's metadata-first layout, so
  r3 leaves it as placed (refused visibly) and records it.
- **FINDING3 / LORA10-N1** (`FINDING3_UNDECLARED_SOCKETS.md`, updated):
  - **What it is.** A schema/type-validation gap, not a demonstrated prompt rejection. The cited core source validates
    only declared inputs and passes undeclared linked values for `ACCEPT_ALL_INPUTS`.
  - **Why it's unchanged in r3.** Closing B1 doesn't need it. Declaring the two inputs would mean a schema edit plus a
    regenerated manifest in the established approved environment, which is outside this PC.
- **Limits of the evidence** (LORA10-N2 still applies).
  - These are converted-code tests over fake hosts, not an original-vs-converted browser/backend differential.
  - The fake "r4a" keeps live's Promise-returning `extend`.
  - With synchronous delivery, the fake's positional placement can trigger an intermediate rows write during placement,
    in Loader and Hook alike (pre-existing). The write-once assertions count from the end of placement.
