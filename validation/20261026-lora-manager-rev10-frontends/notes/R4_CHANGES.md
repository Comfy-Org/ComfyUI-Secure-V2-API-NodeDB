# LoRA Manager rev 10 r4: Create Hook rows through the LORAS setter normalization (review of r3)

- **Review:** Root `review-lora-rev10-r3-20261026`; the finding was confirmed in MERVYN m_d0a1b23c2f.
- **Base:** r3, frozen at `coordination/lora-rev10-frontends-r3-20261026/` (SHA256SUMS `93fbbd4f…`).
- **Corpus:** main `605d0897`. The LoRA subtree is unchanged since `a45522ff`.
- **This package:** a new, separately sealed folder. Nothing is staged, published, deployed or committed.

## The finding and the fix

**The finding.** In the original, every LORAS node, Create Hook included, gets its rows widget from one factory
(`web/comfyui/loras_widget.js`, `LORAS(node)`). Every assignment goes through that widget's setter (812-834), which:
- treats a non-array as `[]`;
- keeps the **last** duplicate of a name;
- sets `clipStrength = clipStrength || strength`, so 0 becomes the strength;
- defaults `expanded` to `clipStrength != strength` when it isn't set;
- defaults `locked` to false.

**Where Hook writes rows.** The original Create Hook assigns rows in two places, both through that setter:
- `loadedGraphNode` (`create_hook_lora.js` 117-135). It reads the **raw** saved array, because
  `getWidgetSerializedValue` (`utils.js` 148-159) returns `widgets_values[index]`, merges `mergeLoras(text, rawRows)`,
  and assigns the result.
- the text callback.

**The gap.** r3's Hook wrote raw `mergeLoras` output, so a saved row with strength 1 and `clipStrength: 0` restored
with 0. Both backends consume `clipStrength`, so this is observable. r3's H1 expectation ("raw native values") was wrong.

**The fix** (`create_hook_lora.js` only; it imports `normalizeRows`).
- `setRows` now normalizes every rows write: automatic restore, text edit and `restore()`. It uses `normalizeRows`, the
  setter normalization the Loader (r2) and WanVideo (r3) already use, plus the owned row bounds.
- The merge order stays Hook's own: merge the raw saved rows, then normalize once.
- A normalization error, meaning rows outside the owned bounds, is caught and logged, and the rows are left as placed.
- **Unchanged.** No other file changes. Loader, Stacker, Prompt, Text and WanVideo are byte-identical to r3, and
  there's no API, schema, manifest or hold change.

| File | sha256 |
|---|---|
| `create_hook_lora.js` (r4) | `a6deaf88e0c4413d970a3a3640a36eae8777c824bada9e39fb574595167eddfa` |
| the other 10 candidate files | byte-identical to r3 (`diffs/r4-vs-r3/` holds only this file) |

## Tests

- **How it was run.** `tools/run_rev10_tests_r4.sh` uses the same node command and permission model as r1–r3: node
  v25.9.0 `--permission`, no `--allow-net`, no child processes, reads only inside this package, writes only under the
  results folder. The tree is `assembled/` (47 files from main `605d0897` plus the candidate overlay).
- **Run 1** (`results/`, kept as recorded): 62/64.
  - H2 failed in both modes on a stale expectation. Its saved rows were already setter-normal, so with parity the
    native merge correctly writes nothing, while r3's raw merge had written once.
  - The same H2 failure shows in every mutant's list there.
- **The H2 correction.** H2 now uses the same rows without `locked`, as older saves have (the nunchaku example's rows
  lack it too). The setter must then normalize them, adding `locked: false`, in exactly one write. Already-normal saves
  need no write, which every re-save idempotence check covers.
- **Run 2** (`results-2/`, the recorded pass): **64/64 passed.**
  - The report `results-2/REV10_UNIT_TESTS.json` has sha256
    `22cb639b669b8aebb58faa1332250b1b45e59f5fd875bd932c746762a54c3237`; the repro run was identical.
  - It covers r3's 60 (H1/H2 corrected) plus 4 new:

| ID | Case |
|---|---|
| H1 sync/async | corrected: Hook original-format restore gives `normalizeRows(mergeLoras(text, rawRows))`, which here equals the saved rows exactly |
| H2 sync/async | corrected fixture: converted `[text, rows]` with rows lacking `locked`. Not migrated; the native merge through the setter writes once and adds `locked: false` |
| H5 sync/async | new. A Hook original-format save with: a row of strength 1 and `clipStrength: 0` (restores 1); a duplicate name (the last entry is kept); a row without `expanded` (the merge sets false); a text-only row with clip ≠ strength (`expanded: true`); `locked: false` throughout. Checked against **hand-written** setter values, with re-save idempotence, and the converted save of the same rows restores the same |
| H6 sync/async | new. Hook text edits also write setter-normal rows: typing `<lora:e:1:0>` gives `clipStrength` 1 and `locked: false`, and the typed text is not rewritten |

- **Mutants** (`results-2/MUTANTS.txt`): all seven fail exactly their expected tests.
  - r3's six (two expected sets now include H5):
    - echo order → R2.sync;
    - Loader/Prompt migration disabled → M1–M3 in both modes;
    - migration after the re-merge → M1.sync and both M3 runs;
    - Hook `onConfigured` unhooked → both H1 runs, H2.sync and both H5 runs;
    - Hook shape guards removed → H1.async, H3.async and H5.async;
    - Text/Wan migration disabled → X1 and V1 in both modes.
  - The new one: Hook rows written raw again → H1, H2, H5 and H6 in both modes.

## Recorded, not changed (out of r4's scope)

- **An `expanded` edge case in older saves (Loader, Stacker, WanVideo).**
  - These normalize the saved rows *before* the merge (r2/r3, reviewed as sound). The original merges the raw rows
    first.
  - For a saved row that lacks `expanded` but has a different clip strength, rev 10 restores `expanded: true` where the
    original restores false.
  - It is UI-only (strength values are identical either way), and none of the pack's real example rows lack
    `expanded`.
  - Per the r4 brief, Loader/Stacker/Prompt are not changed. It's listed for the reviewer.
- **FINDING3** is unchanged: a schema/type-validation gap, not a demonstrated prompt rejection (see its note).
