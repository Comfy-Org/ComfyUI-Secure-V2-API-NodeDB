# Browser smoke plan: rgthree-comfy revision 5 candidate r2

For BART and JERRY's existing browser harness: the Playwright runner used for the rgthree and Label acceptance runs. It
records page errors, console messages, network requests and screenshots.

This candidate is source only. Nothing in this folder was deployed, published or run in a browser. Run the plan only in a
window JERRY has announced.

Changes from r1's plan, following the independent review (`coordination/rgthree-rev5-review-20261020/REVIEW.md`):
- new row **8b**: a ring of pass-through nodes, then toggling a Fast Muter (M1);
- check **9** (the tree-sitter WASM for Power Conductor) is now **required** (L2);
- a list of known pre-existing defects, to record but not count as layout failures (I1).

## What is under test

- **Host:** the live host-stack r3, with `host-entry.mjs` `63d9437e…` and `guest.mjs` `c6b97a15…` served at
  `/secure-nodes/src/`. Preflight: the served hashes match.
- **Pack:** rgthree-comfy revision 5 candidate r2, in the bytes listed in this folder's `STAGE_MANIFEST.json`:
  - `stage/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/` is the tree to serve;
  - `stage/patches/…` is the matching pair.
- **The change under test:**
  - `secure-nodes.json` declares `web_directory: "web"` and no `static_directories`;
  - all 73 `.js` files under `v2/web/` are entry modules served at `/extensions/rgthree-comfy/`;
  - nothing is served under `/rgthree/`.

Two ways to put the candidate in front of the browser. Pick one and record which.

- **A. Install the candidate (preferred).** Use the normal install path in a window, so the backend applies the real
  `web_directory`. Only this mode exercises the backend's `/extensions` list, its file route and its CORS headers.
- **B. Session-only overlay, as for the revision-3 evidence run.** Use the harness's route interception for one session:
  - Answer `GET /extensions` with the live list. Replace the rgthree entries with exactly the 73 URLs below.
  - Answer `GET /extensions/rgthree-comfy/<rel>` from `stage/…/v2/web/<rel>`.
  - Use the same headers the live route sends: `Content-Type` by extension, `X-Content-Type-Options: nosniff`,
    `Cache-Control: no-store`, and the CORS header the live asset origin sends.

  Mode B does not test the backend's own mapping. Record it as "overlay" in the result.

## Preflight (stop if any check fails)

1. The host-stack r3 served hashes match.
2. In mode A, spot-check the served candidate bytes against `STAGE_MANIFEST.json`. Fetch each file, take its sha256, and
   compare it with the path's entry in the manifest:
   - `comfyui/rgthree.js`
   - `comfyui/base_power_prompt.js`
   - `comfyui/base_any_input_connected_node.js` (changed in r2)
   - `common/progress_bar.js`
   - `common/media/rgthree.svg`
3. Run checks 1–8b, 10 and 11 with default settings. Check 9 needs the opt-in Power Conductor, so it runs afterwards, in a
   second page load. In the host settings panel, turn on "Enable Power Conductor (reload required)" (rgthree-comfy →
   Experimental, setting id `rgthree.unreleased.power_conductor.enabled`), then reload.
4. `GET /extensions` lists exactly 73 rgthree URLs, `/extensions/rgthree-comfy/<rel>`, with `<rel>` from the list at the
   end of this plan. None of them is under `link_fixer/`, `models/` or `common/components/`.

## Checks

The pass criteria use the harness's existing records: page errors, console messages, network log and screenshots.

| # | Check | Pass when |
| --- | --- | --- |
| 1 | Module loads | 0 module-load failures for rgthree. Specifically, none of these name an `/extensions/rgthree-comfy/` URL: a page error, an "Error loading extension" console error, a guest `loaderror`, or a `[url mode]` / `[source mode]` error prefix. If the harness can read the host's `loadResults`, all 73 rgthree rows have `ok: true, mode: "url"`. |
| 2 | Network | Every request under `/extensions/rgthree-comfy/` returns 200. There are 0 requests to any `/rgthree/…` path and 0 4xx/5xx under the prefix. Each entry may be fetched up to three times: the host's fallback fetch, the guest's url probe, and the import. `common/media/rgthree.svg` is fetched once and returns 200, so no unhandled rejection from `svgs.js`. The `lib/*.wasm` files are fetched only when Power Conductor runs code (check 9). |
| 3 | Progress bar present | Top-bar badge `rgthree.progress` shows text `Queue: 0` when the queue is idle. Action-bar button `rgthree.progress.jump` ("Show executing node") is present, and so is the `rgthree.menu` button ("rgthree-comfy"). Optionally, queue one small prompt: the badge text changes and then returns to `Queue: 0`. |
| 4 | No addMenuItem / onBeforeConnect refusal rows | 0 console lines match any of these: `a sandboxed addMenuItem needs a string label`, `'onBeforeConnect' is not available to a sandboxed pack`, `(onBeforeConnect`, `menu item ".*" is not available in the sandbox yet`, `(dynamic label)`. |
| 5 | Other rgthree notices are exactly the known F18/F19 ones | Exactly 8 one-time `console.warn` lines starting `[rgthree-comfy] `. Six read `<type>: link fan-out on empty canvas (onUnplacedLink) is not available in the sandbox yet.`, one for each of the six Context types. Two read `all node types: drop-to-import onto a node (onDragOver)` (or `(onDrop)`) `is not available in the sandbox yet.` Any other `[rgthree-comfy] … not available` line fails this check. A queue-subscription "unavailable" notice from `prompt_service.js` (F20) is recorded but does not fail it. |
| 6 | rgthree types registered | All 36 default types are in the node library and construct when added to an empty canvas, with no page error: 24 backend and 12 frontend-defined (lists below). Not expected: `Reroute (rgthree)` (missing in this revision). Also not expected in the default page load: `Power Conductor (rgthree)`, `Dynamic Context (rgthree)` and `Dynamic Context Switch (rgthree)`, which are opt-in and off by default. (Check 9's second load adds Power Conductor.) |
| 7 | Menus (P2 regression) | Right-click a Power Primitive. While its type selector is visible, the menu has exactly "Hide Type Selector Widget". Run it: the selector hides, and the next menu has exactly "Show Type Selector Widget". "Set type" offers STRING / INT / FLOAT / BOOLEAN. Each Context type shows its one "Convert To …" item. |
| 8 | F17 degrades gracefully (P3) | Connect node X's output into Fast Muter A's input, then connect A's output back into X's input, closing a loop. The link is not refused and no "time paradox" alert appears, which is the documented "missing: F17 connection policy" loss. There is no console error. Connecting from a Power Prompt's greyed MODEL output (MODEL input unconnected) is likewise allowed, and the output stays grey. |
| 8b | A ring of pass-through nodes no longer overflows (M1) | Build the ring: a Node Collector C and a core Reroute R. Wire some node K (a KSampler, say) into one of C's inputs. Link C's `Output` into R, then link R's output back into C's free `*` input. Revision 5 accepts that last link, with no alert. Also wire C's `Output` into a Fast Muter M. Then toggle M, rename any node, and change another node's mode. **Pass when** the console and the worker show no `RangeError` and no "Maximum call stack size exceeded", and the page stays responsive. M also lists exactly K: not C, not R and not itself. Toggling M mutes and unmutes K. Repeat once with two Node Collectors wired into each other in place of C and R. |
| 9 | **Required:** WASM assets for Power Conductor | In the second page load (preflight 3), add a Power Conductor, type a short expression into its code widget, and run it. **Pass when** both `GET /extensions/rgthree-comfy/lib/tree-sitter.wasm` and `…/lib/tree-sitter-python.wasm` return 200, and the code runs with no console error. Revision 5 moved the grammar's load path (`common/py_parser.js`), and Power Conductor stays "tested (scoped)" only on a PASS. If the sandbox CSP refuses WebAssembly compilation, this check FAILS, and the refusal is also reported as a host finding. |
| 10 | No errors from other packs | Page errors and console errors attributed to other packs' URLs (`/extensions/<other>/…`) number the same as the latest baseline run, or 0. At least one other converted pack with frontend code (Crystools or KJNodes) still loads all of its entries. |
| 11 | No DataCloneError | 0 occurrences anywhere. |

## Record

For each check, record PASS or FAIL plus:
- the console log, with page and worker messages;
- the network log (HAR) filtered to `/extensions/rgthree-comfy/` and `/rgthree/`;
- the `/extensions` response body;
- screenshots of the top bar (badge), of the Power Primitive menu in both states, and of 8b's ring with M's toggle list;
- the window times and the served hashes.

If anything fails, restore the previous rgthree release by the normal path, and report the failing rows verbatim.

After a PASS of every check, including 8b and 9, the node counts in `SECURE_CONVERSION.md` may be updated. Until then
they stay at revision 4's.

## Known pre-existing defects (record, do not count as layout failures)

These are not revision-5 changes. On the live host the modules involved never loaded before, and now they do, so their
click paths become reachable. Each throws only when clicked; record the error if seen.
- **Settings (rgthree-comfy)** (the rgthree menu or command): `ReferenceError: Node is not defined`. `config.js` opens
  `common/dialog.js`, which reaches `common/utils_dom.js`'s `child instanceof Node`, and a worker has no `Node`. The
  settings themselves stay editable in the host's settings panel.
- **"Star on Github"** (rgthree menu): a `TypeError`, because the worker's `window` stub has no `open`.
- **"Convert … Reroutes"** (rgthree menu): a `TypeError`, because the worker's `window` stub has no `confirm`.

## The 73 entry modules (`/extensions/rgthree-comfy/<rel>`)

`comfyui/` (56):
`any_switch.js base_any_input_connected_node.js base_node.js base_node_collector.js base_node_mode_changer.js
base_power_prompt.js bookmark.js bypasser.js comfy_ui_bar.js config.js constants.js context.js dialog_info.js
display_any.js dynamic_context.js dynamic_context_base.js dynamic_context_switch.js fast_actions_button.js
fast_groups_bypasser.js fast_groups_muter.js feature_group_fast_toggle.js feature_import_individual_nodes.js
image_comparer.js image_inset_crop.js image_or_latent_size.js label.js label_drawing.js menu_auto_nest.js
menu_copy_image.js menu_queue_node.js muter.js node_collector.js node_mode_relay.js node_mode_repeater.js
power_conductor.js power_lora_loader.js power_primitive.js power_prompt.js power_puter.js random_unmuter.js reroute.js
rgthree.js sandbox_limits.js seed.js services/bookmarks_services.js services/config_service.js
services/context_service.js services/fast_groups_service.js services/key_events_services.js utils.js utils_canvas.js
utils_deprecated_comfyui.js utils_inputs_outputs.js utils_menu.js utils_widgets.js widget_controls.js`

`common/` (16):
`comfyui_shim.js comfyui_shim_pnginfo.js dialog.js link_fixer.js media/svgs.js menu.js model_info_service.js
model_info_storage.js progress_bar.js prompt_service.js py_parser.js rgthree_api.js shared_utils.js utils_dom.js
utils_templates.js utils_workflow.js`

`lib/` (1): `tree-sitter.js`

The served tree also has non-entry files:
- `comfyui/rgthree.css` and `common/css/*.css` (6);
- `common/media/rgthree.svg`;
- `lib/tree-sitter.wasm` and `lib/tree-sitter-python.wasm`.

## Expected registered types (check 6)

**Backend (24, from `secure-nodes.json`):**
- Any Switch;
- Context, Context Big, Context Merge, Context Merge Big, Context Switch, Context Switch Big;
- Display Any, Display Int;
- Image Comparer, Image Inset Crop, Image Resize, Image or Latent Size;
- KSampler Config, Lora Loader Stack, Power Lora Loader;
- Power Primitive, Power Prompt, Power Prompt - Simple, Power Puter;
- SDXL Empty Latent Image, SDXL Power Prompt - Positive, SDXL Power Prompt - Simple / Negative;
- Seed.

Every name carries the suffix ` (rgthree)`.

**Frontend-defined (12):**
- Bookmark, Label;
- Fast Actions Button, Fast Bypasser, Fast Muter;
- Fast Groups Bypasser, Fast Groups Muter;
- Mute / Bypass Relay, Mute / Bypass Repeater;
- Node Collector, Node Combiner, Random Unmuter.

Every name carries the suffix ` (rgthree)`. Node Combiner's title is "‼️ Node Combiner [DEPRECATED]".
