# Secure conversion report: ComfyUI-Inspire-Pack

- Pinned commit: `d23db9aa544de9a6d4c609cb7005fa9e0d42031d` (version 1.23)
- Status: **4 nodes converted**, with their original ids, schemas and display names. Round 1:
  - `LoadImagesFromDir //Inspire` (Load Image Batch From Dir)
  - `LoadImageListFromDir //Inspire` (Load Image List From Dir)
  - `ChangeImageBatchSize //Inspire`
  - round 2: `GlobalSeed //Inspire` (Global Seed), with its seed control (see "Round 2: Global Seed").
- **The pack's other declared nodes are not registered yet.** Refusal stubs will follow in a later round. Several of their modules need the Impact Pack and ComfyUI host modules at import time.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used is also in 0b86765f, so no minimum base applies.
- Frontend: `web/global_seed.js` (round 2). The pack's `js/` extensions belong to nodes not converted yet. Routes: none.

## How it runs
- `__init__.py` registers only `secure_inspire.py`. The original imported all thirteen `inspire/` modules.
- `_sn_image.py` holds the three nodes. Their value-handling lines are the original's (`inspire/image_util.py`), in the original order. Each change is marked `V2:` in the code:
  - **Listing:** the folder is listed through the SDK (`ctx.assets.list`; `_sn_dir.py`), not `os.listdir`.
  - **Reading:** each image's bytes are read through the SDK (`ctx.assets.resolve` + `read_bytes`) and opened by the pack's own PIL lines.
  - **Resizing:** `comfy.utils.common_upscale` is a line-for-line copy (`_sn_comfy_utils.py`), because a guest cannot import ComfyUI.
- Permissions: `assets` for the two folder loaders; none for ChangeImageBatchSize.
- `pyproject.toml` declares `requires-python = ">=3.13,<3.14"`. Its `dependencies` are empty: the converted nodes import neither matplotlib nor cachetools.

## Folders
The original reads any folder on the host. Secure Nodes V2 reads only ComfyUI's managed folders:
- `input/<folder>`, `output/<folder>` or `temp/<folder>` select that folder. The original resolves these relative to the ComfyUI folder too.
- Any other relative path, e.g. `my_frames` or `my_frames/day1`, is a folder inside the input folder.
- Absolute paths (`C:\...`, `/...`, `\\server\...`) and `..` are refused by name, at validation and at execute.

## Parity (tier 1, CPU gate)
`tests/test_comfyui-inspire-pack_parity.py` runs the original node and v2 on synthetic image folders:
- RGB and RGBA images of mixed sizes, an EXIF-rotated JPEG, upper-case extensions, non-image files and a sub-folder.
- The original reads them by absolute path; v2 reads them through the SDK. Outputs are compared exactly.
- Covered: every sort method v2 offers, start_index (including -1), image_load_cap, the output folder, folders with no images, the original's error messages, and `IS_CHANGED` vs `fingerprint_inputs`.
- The schemas are checked through the guest class and the host proxy; ChangeImageBatchSize is checked for growing and shrinking batches.

`tests/test_comfyui-inspire-pack_guest.py` runs the nodes through the host proxy in a real guest process.

## Known differences
1. **Folders:** only folders inside ComfyUI's input, output or temp folder are read (see above). File paths from LoadImageListFromDir are the folder as entered, joined with the file name.
2. **"None" sort, or no sort saved:** files come in name order. The original used the order the host filesystem lists them in, which differs between systems.
3. **Datetime (ASC/DESC) sorts are refused:** the SDK does not expose file modification times.
4. **Edge cases:**
   - Sub-folders are not listed. The original raised an AttributeError for a sub-folder named like an image.
   - An existing but empty folder reports "cannot be found" instead of "No files in directory".
   - A folder can list at most 4096 files, and an image can be at most 64 MiB.
   - No image left after filtering, start_index and the cap: not a difference. The original returns nothing, which ComfyUI rejects with `TypeError: object of type 'NoneType' has no len()`. A V3 node returning nothing would finish without outputs, so v2 raises that same error.
5. **pillow-jxl:** if it is installed, the original also accepts files ending in `.`, `j`, `x` or `l`, because of how it extends its extension list. A guest has no pillow-jxl.
6. **Errors:** an error raised while a node executes in the guest reaches ComfyUI as a transport error (`WireError`), whose text is the original exception type and message.
7. `/object_info` `python_module` is the secure mount path.

## Round 2: Global Seed
- **The node.** `GlobalSeed //Inspire` has the original's id, inputs, category and display name. As in the
  original, it is an output node with no outputs that does nothing when it runs.
- **How the original controls seeds.** It does this around the prompt:
  - `js/prompt.js` sends a map of the root graph's seed widgets with the queued workflow;
  - the on-prompt handler in `inspire/inspire_server.py` rewrites the queued prompt (`prompt_seed_update`)
    and the workflow embedded in the outputs (`workflow_seed_update`);
  - `js/seed.js` applies the result to the widgets.
- **How V2 does it.** V2 does not let a pack rewrite the queued prompt. So `web/global_seed.js` applies the
  same rules to the graph just before the prompt is built (`comfy.queue.onBeforeRun`), and the prompt then
  carries them. `control_seed`, `SeedGenerator` and `max_seed` (2^32 - 1) are ported:
  - control before generate: the value is controlled first; every seed comes from it; `last_seed` keeps the
    previous value; the embedded workflow records action `fixed`, so it reproduces the run;
  - control after generate: seeds come from the current value; the next value is applied once the run is
    submitted (`comfy.queue.onAfterRun`);
  - targets: in prompt order, the `seed` / `noise_seed` widgets of root-graph nodes that reach the prompt
    (not muted or bypassed, a backend node that declares the input), still widgets, and not fed by a link;
  - `$GlobalSeed.value$` in any text the prompt carries becomes the value;
  - the last GlobalSeed in the prompt controls; a muted or bypassed one controls nothing.
- **Tests.** `tests/test_global_seed.py` runs the original's own functions, taken from
  `inspire_server.py`, against `tests/global_seed_harness.mjs` running this module (node.js), on the same
  graphs. It compares the executed prompt, the embedded workflow and the widgets after each run:
  - before/after modes, every deterministic action, wrap-around at 0 and max_seed;
  - muted, bypassed, converted and linked seeds, and a frontend-only node with a `seed` widget;
  - a muted GlobalSeed, and placeholders, including one inside a subgraph;
  - random actions, by their rules.
  It also checks the node's schema against the original's `INPUT_TYPES`, plus validation and a guest
  execution.

### Known differences (Global Seed)
1. **Only frontend runs are controlled.** A prompt queued through the API without the frontend is not
   seed-controlled. The original's handler did nothing for such a prompt either: it needs the widget map
   that only its frontend sends.
2. **Placeholder text in the embedded workflow.** Text holding `$GlobalSeed.value$` is replaced in the graph
   while the prompt is built, then restored. The workflow embedded in that run's outputs carries the
   replaced text, where the original's kept the placeholder.
3. **The GlobalSeed node's own prompt inputs.** In a control-before run they carry action `fixed`, because
   the graph holds `fixed` while the prompt is built. In a control-after run they carry the value used
   (the original's prompt carried the next one). The node ignores its inputs.
4. **Connected seed widgets.** With the current frontend, a seed whose socket is connected keeps its widget,
   and it is left alone here. The original's frontend turned such a seed into a converted widget, which
   it skipped too.
5. **Several GlobalSeed nodes.** Every GlobalSeed shows the controlling node's value. The original showed
   the value of the last one in workflow order.
6. **The host's own control.** A seed widget's `control_after_generate` still runs as the host applies it.
   If the host is set to apply widget controls before queueing, that control may run after this one.
