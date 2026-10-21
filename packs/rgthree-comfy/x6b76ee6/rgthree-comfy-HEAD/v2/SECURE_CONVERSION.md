> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request (revision 4).
> Revision 5 (2026-10-20) is a source-only candidate. It changes the served frontend layout and has not been browser-tested.
> Nodes: 37 of 40 upstream converted; 5 tested (scoped), 14 converted but untested/partly tested,
> 21 partial or missing: 18 converted with a behaviour blocked by a missing host capability, 3 missing or pending.
> These are revision 4's counts. They stay unchanged until a browser test of revision 5 passes.
> Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — rgthree-comfy (`rgthree-comfy`)

## What this revision contains

- **Base:** revision 4 (corpus PR #17), as on corpus main (`d6271b5c`). Revision 4 was built on revision 3 (PR #13).
  Revision 2 is kept in the corpus but held from the registry, because its `prompt_service.js` raises DataCloneErrors in
  the sandbox; revision 3 fixed that.
- **Changed in revision 5** (candidate, source only). Three pack-side problems from a live browser smoke test on
  host-stack r3:
  - **Served layout.** `secure-nodes.json` declares `web_directory: "web"` (was `web/comfyui`). It no longer declares
    `static_directories` (was `rgthree -> web`): the live host parses that field but never serves it. The host serves
    everything under `web/` at `/extensions/rgthree-comfy/`, and every `.js` under it is an entry module. The pack chooses
    no URL prefix; the host assigns `/extensions/rgthree-comfy/`.
    - On revision 4, 27 of the 56 `web/comfyui` entry modules could not link. The live release is older, and 26 of its 54
      cannot, which is the smoke test's count. They import `../../rgthree/common/…`, which resolves to the unserved
      `/rgthree/common/…`. Those 16 imports, in 13 files, now read `../common/…`.
    - `common/py_parser.js` loads `tree-sitter-python.wasm` from `new URL("../lib/…", import.meta.url)`. Before, it used
      `rgthree/lib/…`, which a worker resolves against its own location.
    - `common/shared_utils.js` builds its page URL (`openWindowAndWaitForMessage`) from `import.meta.url` instead of
      `/rgthree/…`. Nothing calls it, here or upstream.
    - `comfyui/rgthree.css` takes its logo from `../common/media/rgthree.svg` instead of the old `/rgthree/logo.svg` route.
      Nothing in v2 loads this stylesheet. If something did, the static logo would draw in black, where the route drew it in
      `#93c5fd`.
    - `__init__.py`'s `WEB_DIRECTORY` follows (`./web`). The secure loader reads only `secure-nodes.json`.
    - In `secure-nodes.json` only those two top-level keys change, edited by hand; every node schema is unchanged. The
      backend's generator (`backend/scripts/generate_rgthree_manifest.py`) still writes the old two values, so it needs
      the same change before the next regeneration.
    - The link-fixer and model-browser pages leave the served tree: `web/link_fixer/` and `web/models/`, and the pages'
      custom-element base class `web/common/components/base_custom_element.js` (10 files). The pages are not delivered
      (F16). Served from `web/`, their HTML would run pack code as a top-level page on the host's origin, outside the
      sandbox. `base_custom_element.js` extends `HTMLElement`, which throws at evaluation in the worker, so it and both
      `models/` modules would fail as entries. Their sources remain in the pristine tree and in `v2/src_web/`.
    - The extra entries are harmless. The worker imports each entry by its real URL ("url" mode, which this multi-file pack
      already needs), and a module is evaluated once per URL in the worker's realm. 13 of the 17 new `common/` and `lib/`
      entries are already imported by `comfyui/` entries, so each is still evaluated once. The other four
      (`common/link_fixer.js`, `common/menu.js`, `common/utils_templates.js`, `lib/tree-sitter.js`) only define classes,
      functions and constants when evaluated. None registers anything, adds a listener, fetches, or reads a global the worker
      lacks.
    - How the JavaScript was produced: the `.js` files in `v2/web/` are edited by hand, as in every revision. They are not
      built from `v2/src_web/`, which stays an unchanged upstream copy. Upstream's `__build__.py` rewrites imports to the old
      `../../rgthree/common` route and is not used.
  - **Menu labels.** No change was needed. Revision 4 already replaced Power Primitive's label function with two fixed labels
    and a `when` predicate. The live refusal matches an older release, which still has the label function. A static scan
    of every served module finds no `addMenuItem` with a label that is not a string.
  - **Connection filtering.** No module registers `onBeforeConnect` any more (`base_power_prompt.js`,
    `base_any_input_connected_node.js`, `dynamic_context.js`). The host refuses it, so registering it only produced a refusal
    and a console notice. Now there is neither. Each lost behaviour is listed below as *missing: F17 connection policy*. The
    rules are kept, unregistered, as `powerPromptConnectionRule`, `anyInputConnectionRule` and
    `dynamicContextConnectionRule`, for the host's declarative connection policy (F17: `setConnectionPolicy` /
    `SlotPatch.linkable`).
    - The kept loop rule reports through the host's notice (`comfy.commands.notify`) instead of the original's `alert`,
      which a worker does not have. Its answer is unchanged.
  - **Ring-safe link walk.** Without the loop guard, a link that closes a ring is now accepted. The walk that finds a node's
    connected nodes (`walk` in `base_any_input_connected_node.js`) has the original's shape, and only that guard ever
    kept it finite.
    - Unchanged, a ring of pass-through nodes (a Reroute and a Node Collector or Combiner wired into each other) would make
      it recurse until the worker's stack overflowed. That would happen on the next connection change, and again on every
      mode or title change for a Fast Muter or Bypasser fed from the ring.
    - The walk now enters each pass-through node once, and never lists the node it began from. On graphs without rings it
      returns exactly what it did before.
    - A unit test of the module on synthetic graphs, evaluated alone with its three imports stubbed, checks both: rings
      terminate, and 0 differences from revision 4's walk across thousands of graphs without rings.
    - The one loss left is the up-front refusal: rings are allowed, and no longer crash.
  - **Known defects that this layout makes reachable.** They are not caused by revision 5, but `config.js`, `rgthree.js`
    and `comfy_ui_bar.js` now load on the live host. They throw only when clicked:
    - the Settings (rgthree-comfy) dialog (`common/utils_dom.js` uses `Node`, which a worker lacks);
    - "Star on Github" (`window.open`);
    - "Convert … Reroutes" (`window.confirm`).

    The settings themselves remain editable in the host's settings panel.
  - **Evidence:** static, plus the module-level walk unit test; no browser run yet:
    - every served module parses (acorn 8.17.0, and V8 in Node 25.9.0);
    - all 73 entry modules link;
    - every static and dynamic import and every asset URL resolves to a served file under `/extensions/rgthree-comfy/`,
      with two exceptions: the host's own API module `/comfy/api/v2.js`, and two Node-only branches in the vendored
      tree-sitter that a browser never reaches;
    - no `/rgthree/` root reference remains.
- **Changed in revision 4** (host-supported replacements for blocked behaviours):
  - `web/comfyui/context.js`: the "Convert To …" menu item. The original's label was a function of the node's type, and
    a sandboxed menu label must be a string. The item is registered per node type, so its label is the original's text
    for that type, fixed. Where the builder is not handed its definition, there is one item per type, and a `when` shows
    it only on that type. Either way, each Context node shows one item, with the original's label, and it runs the
    original's replacement.
  - `web/comfyui/power_primitive.js`: the original's single "Show/Hide Type Selector Widget" item is now two fixed-label
    items, "Hide Type Selector Widget" and "Show Type Selector Widget". Each is shown only in the state its label
    describes, and both toggle. The menu reads exactly as before.
  - Both `when` predicates read only the node's type or property. They answer correctly on the live host, where
    menu visibility is computed per node, and after the bridge-parity revision that evaluates each node's `when` for a
    right-click on that node.
  - **Tests:** `tests/rgthree_rev4_menus.test.mjs` runs the actual modules three ways:
    - the original (revision 3's modules, where a label may be a function, as upstream);
    - revision 3 under the sandbox's label rule. This is the negative control: both items are refused and missing;
    - revision 4.
    For every Context type, and for Power Primitive through hide → show → hide, the one revision-4 item a right-click
    shows carries the label the original's function returns, and running it does what the original's run does. Every
    other item is unchanged. Result: 1 negative control and 5 cases. All 5 mutants fail at their target case.
- **Changed in revision 3** (no frontend module may be lost because the host refuses one registration):
  - `web/comfyui/sandbox_limits.js` (new). Every registration the host refuses goes through `whereSupported`: a refused
    hook (`onBeforeConnect`, `onUnplacedLink`, `onDragOver`, `onDrop`) or a menu item with a label function costs only that
    behaviour, and is reported once per node type. Any other error is re-thrown.
  - The guarded registrations are in `base_any_input_connected_node.js`, `base_power_prompt.js`, `context.js`,
    `dynamic_context.js`, `feature_import_individual_nodes.js` and `power_primitive.js`. Each lost behaviour is listed under
    *Blocked behaviours* below.
  - `web/common/prompt_service.js`: the queue members the sandbox cannot carry yet (`queue.onPendingChanged`,
    `queue.onInterrupted`) are treated as unavailable and reported once. The progress bar shows less instead of raising a
    DataCloneError at login. `queue.pending()` is read when its answer arrives.
  - **Browser evidence:** a read-only run on the live host, with these revision-3 files served to that one browser session
    and everything else live:
    - all 54 rgthree entry modules load (live with revision 1: 43);
    - no DataCloneError;
    - the 10 previously failing node types register and construct;
    - 29 one-time notices name each lost behaviour.
- **Changed in revision 2** (kept):
  - Backend (`py/secure_nodes.py`, `py/_secure.py`, `secure-nodes.json`). Three fixes found by original-comparison runs:
    - Lora Loader Stack resolves the exact selected name and declares an input validator, so real selections pass prompt
      validation and missing names are rejected there.
    - SDXL Empty Latent Image builds its latent with the SDK's latent op and now carries `downscale_ratio_spacial`, as the
      original does.
    - Power Prompt and SDXL Power Prompt - Positive apply prompt-tag LoRA strengths outside ±100, as the original does.
  - `secure-nodes.json` regenerated with the backend's manifest generator plus its `validation_inputs` fix, which is sent to
    the backend owner for review. Lora Loader Stack now carries its validator's argument names. Every node also gains
    `"loop_boundary": null`, which current Core's schema adds. Node schemas are otherwise unchanged.
  - `web/common/rgthree_api.js`: `getLoras` reads the LoRA catalogue through the public models API
    (`comfy.models.list('loras')`). The pack names the folder and the host chooses the route, instead of the pack fetching
    the core route `/models/loras`, which a sandboxed pack may no longer reach. 1 negative control plus 4 hermetic cases.
    The host must provide `comfy.models.list` for the list to load.
  - This report:
    - dispositions updated from the backend original-comparison runs;
    - two refused-technique descriptions corrected (Power Puter; runtime writes in the pack folder);
    - one technique added (the bundled host-update script).
- **Revision 1** (kept): the registered Label revision (draft PR #6) plus 16 tested frontend files: the 14-file first repair
  tranche, `display_any.js` (F14), and `media/svgs.js` (worker-safe logo URL).
- **Held back** (listed as open):
  - The Reroute definition and the F01 connection-layout port, which wait on host renderer prerequisites S01–S04. All four
    pass their tests, but the deployed frontend does not yet carry S01–S03. A combined S01–S04 frontend patch against the
    deployed sources is in preparation.
  - The optional Dynamic Context backend, which waits on the repeated-output API.
- **Resolved since revision 1:** the startup callback error (`comfy.defs.onRefreshed` inside the sandbox). The host fix is
  deployed and passed browser acceptance on 2026-10-15: no DataCloneError at login, and a refresh reaches the pack's
  worker.

## Provenance

Upstream https://github.com/rgthree/rgthree-comfy at commit `6b76ee6f2c5a007710b5a16f97c94330d6ecc871`
(key `x6b76ee6`). The pristine tree beside `v2/` is byte-exact at that commit (258 files). `v2/src_web/` is an unchanged
copy of upstream's TypeScript sources, kept for reference. The converted, served frontend is `v2/web/`; it is edited by hand
and is not built from `v2/src_web/`. Upstream has
40 node IDs: 37 enabled by default and 3 opt-in (Dynamic Context, Dynamic Context Switch, Power Conductor).
Of the defaults, 24 have Python classes and 13 are frontend-only.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode). "Tested (scoped)" means every
part the node has upstream (backend and/or custom frontend) passed executed original-comparison tests and no
pack-side gap is open. Deployment-wide gates (live browser, asset delivery, gVisor) still apply to every node.

| Node id | Disposition | Evidence or gap |
| --- | --- | --- |
| `KSampler Config (rgthree)` | tested (scoped) | Backend native cases pass; no custom frontend. |
| `Power Conductor (rgthree)` | tested (scoped) | Opt-in. The tested repair ships here: numeric modes/IDs, explicit labels via `getLabel`, pack-owned group toggles. Revision 5 moves the load path of its grammar (`common/py_parser.js`); the browser smoke test's required check 9 covers that. |
| `Image Resize (rgthree)` | tested (scoped) | Backend native cases: 150/150 equal the original. That is 10 sizes × 5 scaling methods × 3 fit modes, compared tensor-for-tensor with current Core's scaling. No custom frontend. |
| `Lora Loader Stack (rgthree)` | tested (scoped) | Fixed in revision 2: exact-name resolution (the previous v2 fuzzy-matched names) and an input validator. Backend native cases: 8/8 equal the original. Validator checks: 21/21, run in the Guest. One accepted difference, listed below. No custom frontend. |
| `SDXL Empty Latent Image (rgthree)` | tested (scoped) | Fixed in revision 2: the latent carries `downscale_ratio_spacial` like the original. Backend native cases: 72/72 equal the original. No custom frontend. |
| `Any Switch (rgthree)` | converted, partly tested | Backend native cases pass. F01 connection layouts are not in this revision. |
| `Display Any (rgthree)` | converted, partly tested | Backend native cases pass; the F14 serialization fix ships here. F01 is open. An own-node PNG metadata candidate passed separately and is not in this revision. |
| `Display Int (rgthree)` | converted, partly tested | Backend native cases pass; F14 ships here. F01 is open. |
| `Fast Groups Bypasser (rgthree)` | converted, partly tested | Tested repair ships here (row state, graph-scoped identities, saved filters). F10 fit-group navigation is open. |
| `Fast Groups Muter (rgthree)` | converted, partly tested | Tested repair ships here. F10 is open. |
| `Image Inset Crop (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Image or Latent Size (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Label (rgthree)` | converted, partly tested | Browser: Classic 7/9 edits persist, Vue 8/9. The remaining focus race is a host renderer fix, still pending. |
| `Power Lora Loader (rgthree)` | converted, partly tested | Backend native cases pass. The tested repair ships here: authored model info, row info actions, stale-request guard. Since revision 2 its LoRA list comes from `comfy.models.list('loras')`. Open: F01, F03, F04, F13. |
| `Power Puter (rgthree)` | converted, partly tested | Backend native cases pass on the bounded evaluator. F03 and F04 are open. |
| `Seed (rgthree)` | converted, partly tested | Backend native cases pass. An own-node PNG metadata candidate passed separately and is not in this revision. F01 is open. |
| `Image Comparer (rgthree)` | converted, partly tested | Backend native cases: 5/6 equal the original, including preview pixels and PNG metadata. With an empty image batch, v2 raises where the original skips; this is open. The comparer widget is untested, and F01 is open. |
| `Power Primitive (rgthree)` | converted, partly tested | Backend native cases pass. Since revision 4 the "Show/Hide Type Selector Widget" entry is two fixed-label items, and a right-click shows exactly the one the original showed; a differential test against the original's label function covers both states and the toggle. "Set type" works. The rest of its frontend is untested. |
| `Bookmark (rgthree)` | converted, untested | Frontend-only; its button-settings repair ships here. F09 (hidden-subgraph navigation) and F11 (keyboard) are open. |
| `Context (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Context Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Context Merge (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Context Merge Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Context Switch (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Context Switch Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 is open. |
| `Random Unmuter (rgthree)` | converted, PARTIAL | The tested failed-attempt cleanup repair ships here. Missing: F17 connection policy — the cycle guard's up-front refusal of a link that loops back on itself. Such a ring is now accepted, without crashing. F07 (independent choice per batch item) and F01 are open. |
| `Power Prompt (rgthree)` | converted, PARTIAL | Fixed in revision 2: prompt-tag LoRA strengths outside ±100 apply as in the original. Backend native cases: 72/72 equal the original. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). The rest of the frontend is untested; F01 is open. |
| `Power Prompt - Simple (rgthree)` | converted, PARTIAL | Backend native cases: 16/16 equal the original. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). The rest of the frontend is untested; F01 is open. |
| `SDXL Power Prompt - Positive (rgthree)` | converted, PARTIAL | Backend native cases pass, including the revision-2 prompt-tag strength fix. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). F01 is open. |
| `SDXL Power Prompt - Simple / Negative (rgthree)` | converted, PARTIAL | Backend native cases: 36/60 equal the original on current Core. In the other 24, the original's sized SDXL encode is broken on current Core and returns no conditioning, while v2 returns the conditioning the original intends; this is an accepted difference, listed below. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). F01 is open. |
| `Fast Actions Button (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F01 and F11 are open. |
| `Fast Bypasser (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F01 is open. |
| `Fast Muter (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F01 is open. |
| `Mute / Bypass Relay (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), refusing the same node on a second input, and keeping its output to a Mute / Bypass Repeater. Otherwise untested. F01 is open. |
| `Mute / Bypass Repeater (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), refusing the same node on a second input, and its output only to the node types that read it. Its two Relay rules still hold after the fact: a Relay input is disconnected again while a toggler is on its output, and its output slot is removed while a Relay drives it. Otherwise untested. F01 is open. |
| `Node Collector (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), and refusing the same node on a second input (also through a reroute). Otherwise untested. F01 is open. |
| `Node Combiner (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), and refusing the same node on a second input (also through a reroute). Otherwise untested. Legacy node. F01 is open. |
| `Reroute (rgthree)` | missing | The frontend definition is not in this revision. A candidate exists, and host prerequisites S01–S04 pass their tests (S04's final run: 418/418). They are not yet all in the deployed frontend. F05 and F06 are open. |
| `Dynamic Context (rgthree)` | pending capability | Opt-in, disabled upstream by default. Needs a public repeated-output API (F02); a runtime test of that candidate is approved. Missing: F17 connection policy — refusing another Dynamic Context's context output on a non-base input. |
| `Dynamic Context Switch (rgthree)` | pending capability | Same as Dynamic Context. |

## Refused techniques (never-do) and their public replacements

No whole user feature is refused. Only these techniques are; each feature they served has a public
replacement or is listed as *not yet* with its prerequisite. Line numbers refer to the pristine upstream tree.

1. **Patching host classes, prototypes and global tables.** This changes behaviour for every node and every pack in the session.
   Upstream instances:
   - `LGraphCanvas.prototype.processKey` (web/comfyui/services/key_events_services.js:17–18);
   - `drawNode` and `getNodeOnPos` (web/comfyui/label.js:132–145);
   - `LiteGraph.isValidConnection` (web/comfyui/utils.js:688);
   - `slot_types_default_out` (web/comfyui/context.js:113–115, dynamic_context_base.js:184–188);
   - `LiteGraph.ContextMenu` (web/comfyui/menu_auto_nest.js:10);
   - `processMouseDown` (web/comfyui/rgthree.js:249–250);
   - `drawGroups` (web/comfyui/feature_group_fast_toggle.js:85–86).

   *Replacements:* per-type `comfy.defs.extend` hooks, `isTypeCompatible`, public slot handles, and the Label
   presentation/canvas APIs. Not yet: group-header toggles (F08) and keyboard shortcuts (F11).
2. **Reading host-private objects or symbols** (`Object.getOwnPropertySymbols` on widgets,
   web/comfyui/utils_deprecated_comfyui.js:10). This crosses the isolation boundary and breaks between versions. *Replacement:* public widget
   handles (`getLabel`, `getOptions`, `getValue`).
3. **Injecting into host DOM** (`app.menu.settingsGroup.element.before`, web/comfyui/comfy_ui_bar.js:18,84; progress
   bar and message containers on `document.body`, web/comfyui/rgthree.js:222–229, 613–624). The host owns its DOM. *Replacement:* public
   chrome contributions (action buttons, top-bar badges) and `comfy.ui`. Not yet: the two-track progress-bar presentation (F12).
4. **Mutating the raw link table** (`app.graph.links[...]`, web/comfyui/reroute.js:307–430). This bypasses validation and undo
   and can corrupt graphs. *Replacement:* public link and slot handles. Not yet: Reroute insertion (F05).
5. **Intercepting or rewriting the built prompt** (`app.graphToPrompt` / `api.queuePrompt` wrappers, web/comfyui/rgthree.js:499–508,
   web/common/prompt_service.js:85). That exposes and alters other nodes' data. *Replacement:* public queue hooks
   (`onBeforeRun`, `onAfterRun`). Not yet: per-submission preparation (F07) and API-workflow import (F13).
6. **Hijacking in-flight canvas gestures** (`canvas.connecting_links`, web/comfyui/reroute.js:53, 116–142). The host owns gestures.
   *Replacement:* not yet; needs a host-owned link-gesture contribution (F05).
7. **Enumerating other packs and calling their lifecycle callbacks** (`comfyapp.extensions.map(...)`,
   web/comfyui/rgthree.js:285–293). That interferes across packs. *Replacement:* none needed; the host runs each pack's own hooks.
8. **Unrestricted attribute access in Power Puter's expression interpreter.** It does not call `eval`, but it resolves arbitrary
   attributes of live objects (`getattr(item, attr)`, py/power_puter.py:569), guarded only by a short blocklist. That exposes
   host internals to workflow text. *Replacement:* the bounded evaluator in `v2/py/safe_puter.py`.
9. **Host-wide VRAM purge** (`purge_vram` → `unload_all_models` / `soft_empty_cache`, py/power_puter.py:63–74, 152).
   This evicts other users' models. *Replacement:* none; the host manages memory.
10. **Writing to the host's file system at runtime, and serving it from raw routes on the host server:**
    - deleting ComfyUI's `web/extensions/rgthree*` with `shutil.rmtree` at import (`__init__.py:86–92`), which is outside the pack;
    - writing `rgthree_config.json` into the pack's own install folder (py/config.py:49,55);
    - JSON writes and removes (py/utils.py:128,149);
    - userdata files under the pack's folder (py/utils_userdata.py:21–29). The path join there has no `..` check, so a
      crafted name can reach outside the folder;
    - model-info sidecars written next to model files (py/server/utils_info.py:452);
    - the `/rgthree/api/*` routes (py/server/*.py).

    *Replacements:* public settings and pack storage (`services/config_service.js`, `common/model_info_storage.js`) and core
    authenticated routes. Not yet: provider-backed model info (F03) and the JS↔Python storage bridge (F04).
11. **Disclosing absolute host model paths** (`folder_paths.get_full_path`, py/power_lora_loader.py:72,
    py/server/routes_model_info.py:152–160, py/server/utils_info.py:416). That exposes the host layout. *Replacement:* logical
    names through the `assets` permission.
12. **Unaudited network fetches by the pack** (Civitai via `requests`, py/server/utils_info.py:327–339; update
    check via `aiohttp`, py/pyproject.py:49–56). *Replacement:* not yet; needs an admitted metadata provider (F03).
13. **Updating the host installation and other packs.** The bundled `__update_comfy__.py` script runs `git pull` across
    ComfyUI and every custom node, and runs `git restore .` where local changes block the pull. That rewrites code the pack
    does not own. *Replacement:* none needed in a pack. v2 never imports or runs the script (it is pristine-only); the host's
    own tooling updates installations.

## Accepted differences

- **Lora Loader Stack.** An invalid LoRA name is reported as `custom_validation_failed` on all four selector inputs, with
  the details prefixed `lora_0N - `. The original reports one `value_not_in_list` on the offending input. After the prefix,
  the details text is the original's. Cause: Core reports a failing `validate_inputs` once per validator input.
- **SDXL Power Prompt - Simple / Negative.** With CLIP width and height set, v2 returns the conditioning that the original
  computes with its intended (pre-V3) SDXL encode. On current Core the original's call fails and returns no conditioning.
  With an SD1 CLIP, v2 falls back to the plain encode described by the original's own log message.

## Blocked behaviours (missing host capability, not refused)

Each of these needs a host capability that does not exist yet; none is a refused technique.

- The two F17 rows are *missing: F17 connection policy*. The host would need their answer synchronously, so it refuses
  `onBeforeConnect`. Since revision 5 no module registers it, so there is no refusal and no console notice. The rules are
  kept, unregistered, for the host's declarative connection policy.
- The F18 and F19 rows are still registered, and the host refuses them for the same reason. Since revision 3 a refusal
  costs only that behaviour, never the module, and each is reported once in the console, by node type.
- F20: when the host refuses the queue subscriptions, `prompt_service.js` treats them as unavailable and reports it once
  (revision 3).

| Behaviour | Needs | Nodes |
| --- | --- | --- |
| Connection filtering: the cycle guard's up-front refusal ("time paradox"; a ring is now accepted, and the link walk is ring-safe) and per-node connection rules (the Repeater's two Relay rules still apply after the fact) | Missing: F17 connection policy (`setConnectionPolicy` / `SlotPatch.linkable`), a policy the host can evaluate without a synchronous worker call. Not registered. | Fast Muter, Fast Bypasser, Node Collector, Node Combiner, Mute / Bypass Repeater, Mute / Bypass Relay, Fast Actions Button, Random Unmuter; Dynamic Context (opt-in) |
| Refusing links from disabled outputs | Missing: F17 connection policy, as above. Not registered. | Power Prompt, Power Prompt - Simple, SDXL Power Prompt - Positive, SDXL Power Prompt - Simple / Negative |
| Link fan-out when a link is dropped on empty canvas | A host-owned unplaced-link contribution (F18) | the six Context nodes |
| Dropping a workflow or image onto a node to import its values | A host node-drop contribution (F19) | all node types (pack feature) |
| Progress bar: queue size and interruption updates | Sandbox subscriptions for the published `queue.onPendingChanged` and `queue.onInterrupted` (F20) | rgthree progress bar |

## Pending items (not yet supported)

- F02 — repeated (dynamic) outputs for the opt-in Dynamic Context nodes.
- F03 — model metadata provider: trained words, Civitai details and images.
- F04 — same-user JS↔Python model-info storage continuity.
- F05 — Reroute insertion/reposition during an unfinished link drag.
- F06 — remaining Reroute presentation parity: per-link colour, low-zoom label suppression.
- F07 — Random Unmuter choosing independently for each prompt in a batch.
- F08 — fast toggle actions in group headers.
- F09 — Bookmark navigation into a hidden subgraph with the original viewport offset.
- F10 — Fast Groups navigation that fits the whole group.
- F11 — widget-configured keyboard shortcuts in the sandboxed realm.
- F12 — the original configurable two-track progress bar.
- F13 — Power LoRA Loader rows from API-format workflows; A1111 parameter import.
- F16 — delivery of the pack's model-browser and link-fixer pages. Since revision 5 they are not in the served tree; their
  sources are in the pristine tree and in `v2/src_web/`.
- F17 — connection policy for sandboxed packs (`setConnectionPolicy` / `SlotPatch.linkable`), replacing the synchronous
  `onBeforeConnect`. The pack's rules are kept, unregistered, until it exists. Two notes for the port:
  - `anyInputConnectionRule` already reports through the host's notice rather than `alert`.
  - The per-node rules no longer reach it: the Node Collector, Node Combiner, Relay and Repeater rules sit in each
    definition's `beforeConnect`, which `defineAnyInputConnectedNode` no longer reads. They must be threaded through
    again.
- F18 — host-owned contribution for links dropped on empty canvas (replaces `onUnplacedLink`).
- F19 — host node-drop contribution (replaces `onDragOver`/`onDrop`).
- F20 — sandbox subscriptions for `queue.onPendingChanged` and `queue.onInterrupted`.
- Power Prompt LoRA and embedding insert combos when the model list exceeds the worker's definition bounds
  (needs a public model-catalogue read).

## Open test gates

- Host renderer prerequisites S01–S04 for the F01 layout port (24 node IDs). All four pass their tests. They still have
  to be deployed together as one frontend patch.
- Backend native cases running inside the Guest (sandboxed), and Core prompt validation at runtime for the Lora Loader Stack
  validator. Its checks pass structurally and in the Guest.
- Image Comparer with an empty image batch.
- Original-comparison runs for the eight frontend-only nodes listed as untested.
- Label browser acceptance after the host focus-race fix.
- A browser smoke test of revision 5's layout. Until it passes, the node counts above stay at revision 4's. It checks:
  - 0 module-load failures across the 73 entry modules;
  - the progress badge;
  - asset delivery and CORS under `/extensions/rgthree-comfy/` for the logo SVG;
  - the tree-sitter WASM, which is required: Power Conductor stays "tested (scoped)" only if its grammar loads from the
    new path;
  - no `addMenuItem` or `onBeforeConnect` refusal rows;
  - a ring of pass-through nodes that no longer overflows.
- gVisor admission and whole-pack acceptance review.

## Authority and permissions

- No SDK permissions (12 nodes): the Context family, Any Switch, Display Int, KSampler Config, Seed, Power Prompt - Simple,
  SDXL Power Prompt - Simple / Negative.
- `assets` (4): Lora Loader Stack, Power Lora Loader, Power Prompt, SDXL Power Prompt - Positive.
- `raw` (7): Display Any, Image Inset Crop, Image Resize, Image or Latent Size, Power Primitive, Power Puter, SDXL Empty Latent Image.
- `ui` (1): Image Comparer.
- Frontend: `web_directory` is `web`, served at `/extensions/rgthree-comfy/`. Each of its 73 `.js` files is an entry
  module of the sandboxed pack worker. No static directories and no pack HTTP routes.
  Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. LoRAs, checkpoints, CLIP and embeddings come from the user's managed model catalogue.

