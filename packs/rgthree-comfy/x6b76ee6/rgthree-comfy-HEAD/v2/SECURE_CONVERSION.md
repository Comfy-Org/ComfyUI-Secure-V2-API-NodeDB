> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request (revision 4).
> Revision 7 (corpus PR #74) passed its browser staging on live host stack r3: gate rows S1, S2, S3 and S5.
> Revision 8 (corpus PR #75) is docs and evidence only. It re-derived every row from the staging of revisions 5-7, plus the
> existing backend native cases and module tests.
> Revision 9 R2 (2026-10-26) keeps the F01 expanded layouts and Reroute definition, restores the published contract,
> and removes the unapproved collapsed title-edge socket field (audit V3). F01 is PARTIAL for collapsed title-edge
> sockets pending an approved API or a separate critical-pack shim. No shim or new API is included.
> Revision 9 and R2 have not run in a browser.
> Nodes: 38 of 40 upstream converted; 6 tested (scoped), 13 converted but untested/partly tested,
> 21 partial or pending: 19 converted with a behaviour blocked by a missing host capability, 2 pending.
> Revision 9 moves one row, Reroute (missing to converted, PARTIAL). Every other count waits for browser evidence.
> The revision 8 evidence is in `validation/20261022-rgthree-browser-staging-r5-r7/`.
> Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — rgthree-comfy (`rgthree-comfy`)

## What this revision contains

- **Base:** revision 8 (corpus PR #75, merged as `74264998`). Revision 8 was built on revision 7 (PR #74), revision 7
  on revision 6 (PR #69), revision 6 on revision 5 (PR #54), revision 5 on revision 4 (PR #17), and revision 4 on
  revision 3 (PR #13). Revision 2 is kept in the corpus but held from the registry, because its
  `prompt_service.js` raises DataCloneErrors in the sandbox; revision 3 fixed that.
- **Changed in revision 9 R2:** the draft's pack-local API edit is backed out before publication, as its README
  documented. `comfy-api.d.ts` is byte-identical to main's published `53c296aa7e1f3454ecbf02980a2f3d532d79f7f5e99eda311de689ff56447ded`.
  `connection_layout.js` no longer reads or emits `collapsedPosition`; its last-sent cache and key helper are removed.
  Expanded layouts, grouping, labels, disabled colours, original node IDs and layout math remain unchanged. The
  Reroute source and all other served JS remain byte-identical to the draft. No API addition or shim is implemented.
  The collapsed title-edge socket geometry is an explicit F01 partial for all 24 types, pending MIKE's publication of a
  general API or a separately reviewed critical-pack shim. Draft node disposition counts are retained; no row is promoted.
- **Changed in revision 9** (F01 connection layouts and the Reroute definition). Source and hermetic tests only: nothing
  has run in a browser, so only the Reroute row moves.
  - **F01, connection layouts (24 node IDs).** New `web/comfyui/connection_layout.js`: the Left/Right/Top/Bottom socket
    layouts, the "Connections Layout" menus, "Show Connections" / "Collapse Connections" on the 8 collapsible types,
    hidden labels and greyed disabled sockets. They are saved with the node (`rgthree_connections_v1`), and the
    original's saved slot fields are read on load.
    - It writes published slot patches only: `position`, `direction`, `label`, `color` and
      `colorWhenUnconnected`. The original's `getConnectionPos` class patch stays refused.
    - Sources: the successor tranche (`connection_layout.js` `7fa0e4c2`, 46 original-comparison cases) and MOE's
      draft (`2942aef0`), with the unapproved S02 collapsed-socket dependency removed in R2. The draft registers one `extend` per type
      (no `builder.def`) and uses two fixed menu labels chosen by `when`, never a label function.
    - Any Switch, the six Context types and the any-input base (Fast Muter, Fast Bypasser, Node Collector, Random
      Unmuter, Fast Actions Button, Relay, Repeater) reapply the layout after their delayed stabilization. Their
      per-node records are keyed by graph and node id (successor tranche).
    - Kept from revisions 4-8: no `onBeforeConnect`, the ring-safe walk, the fixed per-type "Convert To …" labels, Merge
      Big's corrected label, `changedNode`, and the Combiner's `graph.replace` upgrade.
    - **PARTIAL in R2:** whole-node collapsed title-edge socket placement is not authored. The draft's
      `collapsedPosition` field was not in a MIKE-published contract (audit V1-V3); a live frontend implementation
      does not make it public API. The pack does not use it, even if a host happens to expose it.
  - **Reroute (rgthree) is defined** (`web/comfyui/reroute.js`, from the consumer `3bed5217`). It resolves as a
    pass-through. It carries type, name and slot colour down chains of reroutes, drops an incompatible target, and
    forwards a widget input's declaration to a Primitive. It keeps the four-sided layout, resizing (40×30 default; a 10 px
    strip flips the sides), rotate, flip, static sizes, the label toggle and "Clone New Reroute". Changes from the
    consumer:
    - no `onBeforeConnect`: the loop guard is kept, unregistered, as `rerouteConnectionRule` (F17);
    - the label's zoom test is `screenRect.width < bounds.width * 0.6`, exact at a scale of 0.6. The consumer's quotient
      hid the label at 0.6 for 19 of the integer widths 1-2000;
    - the geometry relay (L2) is feature-detected. Without it the label is drawn at every zoom, and nothing subscribes to
      `onViewportChanged`;
    - host r3's guest answers are handled. `defs.typeColor` and `isTypeCompatible` arrive there as Promises, and are never
      put into a slot patch. `mergeWidgetConfig` is absent, so the target's own declaration is forwarded. A clone made by
      `graph.add` is wired and selected once the host confirms it, and `graph.add` gets only `NodeInit` members;
    - a layout pass sends only what differs from the slot's snapshot;
    - `DEFINED_NODE_TYPES` lists Reroute, and the module imports both every-node registration modules.
  - **On host r3** (guest `c6b97a15`, and r4a r2's guest `16924bbe`): see *Host behaviour and remaining revision 9 R2 gaps*
    below.
  - **R2 evidence (finite existing suites; Windows Node 25.9.0; no browser):**
    - the successor's 46 original-comparison cases pass on the rebased files;
    - revision 7 r2's 63 module checks pass. Two expectations were updated for Reroute in `DEFINED_NODE_TYPES`;
    - the ring-safe walk test passes;
    - 45 module checks: the exact published contract, zero unpublished slot patches, strict snapshot reads and patch
      keys (768 layout cases times 6 passes), negative controls using the rejected draft, Reroute without L2, the 0.6 boundary at every
      integer width 1-2000, save and reload of layouts, the host r3 answers, registration policy, and stabilization
      timing;
    - AST API-member classification passes against the pinned published contract; the same checker rejects the
      draft's unapproved contract. Exact commands, module hashes and receipts are in the R2 handoff's `tests/results/`.
    - The draft's 31 real-guest checks and its 23 + 22 mutant checks are historical evidence in the original packet.
      They were not rerun for R2 and do not certify this successor. No service or scientific runtime was started.
  - **Counts:** Reroute moves from missing to converted, PARTIAL, so 38 of 40 are converted (was 37). Every other row
    keeps its disposition until the browser F01 slice passes.
- **Changed in revision 8** (docs and evidence only; no served file changes). BART's staging of revision 7 on host r3
  passed its gate. Every row was re-derived from the staging of revisions 5-7 and from the existing backend native
  cases and module tests. The rule was conservative: a row moves only if passing evidence covers every open item it
  lists.
  - **Moved:** Label, from converted, partly tested to **tested (scoped)**. Its row states the scope.
  - **Unchanged:** every other row. Each keeps an open item, or no staging row exercised its frontend behaviour.
    *Re-derived in revision 8* (below the dispositions table) lists every row with its evidence.
  - **Evidence added:** `validation/20261022-rgthree-browser-staging-r5-r7/` holds BART's three result files and the smoke plans they followed.
- **Changed in revision 7** (corpus PR #74). BART's staging of revision 6 on host r3 passed every row except
  three. They share one symptom with two causes: the `onNodeChanged` handlers did nothing on host r3. The Label title refresh, the
  Repeater and the Relay were affected; there were 0 packerrors.
  - **`changedNode` no longer depends on `comfy.graph.id`.** It still needs the node's snapshot filed under the graph
    on screen. After `app.graph.clear()` the graph id changes and no epoch is sent. The guest then files the new
    graph's nodes under a scope its replica does not list, so the event is still dropped, as in revision 6. This is a
    known platform limitation (request R6-12). Revision 6 compared `event.graphId` with
    `comfy.graph.id`. On guest `c6b97a15` that getter answers `graphState.graphId ?? ''` from a replica the host sends
    only with a workflow-load epoch, a gesture to a pack that has read structure, or a requested refresh. It is never sent
    at worker start, so the getter usually read `''`. `root()` and `subgraphs()` answer from the same replica.
    - The node is now looked up by id on the graph on screen, and kept only if its own `graphId` is the event's. The
      guest serves that from node snapshots it already holds.
    - The scopes are only a fallback, for a node in a graph not on screen.
  - **The new value comes from the event.** The guest does not update its copy of a node when the host reports a
    change, so `getTitle()` and `getMode()` still read the old value.
    - The Label lays out `event.to` as its title.
    - The Repeater and the Relay use `changedMode(event)`, which maps the event's mode (litegraph's numbers on host r3)
      to the published names. They fall back to `getMode()`.
  - **Recorded, not changed:** with no pre-selection, "Queue Group Output Nodes" no longer shows for nodes in a group,
    and "Queue Selected" was still listed after a right-click moved the selection. Both items' visibility is computed in
    the worker and read by the host at menu-open.
    - In revision 5 the host never received an answer for these items: its log says "visibility not yet computed …
      showing it", so it showed both.
    - In revision 6 the answer is computed. "Queue Group" reads `comfy.graph.groups()` from the same structure
      replica, which is empty or stale.
    - The host still shows an item whose answer has not arrived, as in BART's R2 run.
    - The items' visibility checks are unchanged since revision 5.
  - **Also affected, not changed (needs request R6-13).** The same stale node copies on host r3 make these lag behind
    a mode or title change:
    - the Relay's mode, when it is driven by its inputs;
    - the Fast Muter / Bypasser toggle state;
    - Node Collector input names.

    Their rows are PARTIAL on host r3 for that reason too.
  - **Evidence:** static and module-level; no browser run yet. See the triage folder.
- **Changed in revision 6** (corpus PR #69). Revision 5 was browser-staged as an overlay on live host stack r3
  (host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`). Every row passed except the required Power Conductor
  row. A static live-readiness audit added four findings. Each finding was checked against the published API
  (`comfy-api.d.ts`) and the live guest's source.
  - **Pack fixes:**
    - **Power Conductor registers when its opt-in resolves.** Revision 5 read the setting once, when the module evaluated.
      The live guest answers a declared setting with its default until the host returns the stored value, so the type never
      registered.
      - Each setting is now declared with an `onChange`, which hears the value change, and on the guest also hears the
        stored value arrive. `config_service.js` announces it as a `config-change`, once per value.
      - Power Conductor registers the first time the opt-in reads as on: when the module evaluates, on that event, or at
        `onReady`. Turning it off still needs a reload.
      - The same event now also reaches the progress badge and the action-bar buttons when a stored value differs from
        the default.
    - **Every-node menu items and drop hooks are registered before the pack defines its own types.** Revision 5 called
      `comfy.defs.extend(/./, …)` from `menu_queue_node.js` and `feature_import_individual_nodes.js`. Those modules could
      evaluate after other modules had already defined their types. The host then logged "will not be applied" 14–19
      times per load, and a Fast Muter lacked both Queue items.
      - `extendEveryNodeType` (`base_node.js`) names each of the 13 types this pack defines (`DEFINED_NODE_TYPES`,
        `constants.js`). A pattern that leaves those 13 out covers every other type.
      - The five modules that call `comfy.defs.define` import both registering modules, so those evaluate first.
      - Maintenance: any type this pack starts defining later must be added to `DEFINED_NODE_TYPES`. The pending
        Reroute definition is one example. The module that defines it must also import both registering modules.
        Otherwise the live guest silently drops that type's every-node items.
    - **Context Merge Big's menu item reads "Convert To Context Merge"**, which is what it does. Upstream labels it
      "Convert To Context Switch" (see *Accepted differences*).
  - **Mitigations for platform gaps.** The platform requests are filed separately.
    - **`onNodeChanged` listeners resolve the node again.** The published event carries the node as a handle. Host r3
      sends a plain copy without methods.
      - Label's title refresh threw `getProperties is not a function`, 3 times per workflow load.
      - The Repeater's and Relay's mode handlers would throw the same way.
      - `changedNode(event)` returns the event's handle, or the same node resolved again in `event.graphId`.
    - **Node Combiner → Node Collector uses `comfy.graph.replace`.** Revision 5 added a Collector and wired it straight away.
      On the live guest a just-added node is unconfirmed, and its input list reads as empty, so the loop that grew the
      inputs never ended.
      - `replace` keeps position, a changed title, colours, mode, shared properties and size. It re-makes the links that
        have a slot.
      - A fresh Collector has one input. So the upgrade leaves a claim that the new Collector's `onCreated` takes: it grows
        the inputs and connects the incoming links that are still unconnected. A Collector restored from saved data (a
        load, a paste or an undo) never takes the claim.
      - `replace` matches slots by name before index, so the Combiner's inputs are first named by their index. An input
        whose source has an empty title, or a title of "Output", would otherwise be mis-wired.
    - **Queue Selected / Group Output Nodes fall back to `{ id }`.** `RunOptions.nodes` is a list of handles, and those are
      sent first. The live guest forwards `queue.run` through a structured clone, which cannot copy a handle
      (DataCloneError). The same nodes are then sent as `{ id }`, which is all the host's `run` reads.
  - **Not changed** (platform gaps; see the host r3 table under *Blocked behaviours*):
    - a mounted widget's value handle;
    - a canvas widget's `widget`, theme and value;
    - `PropertyChangeEvent.setValue`;
    - `comfy.ui.showMenu` with `run` callbacks;
    - a synchronous `comfy.defs.nodeColor`.
  - **Evidence:** static and module-level; no browser run yet.
    - Every served module parses (acorn 8.17.0, and V8 in Node 25.9.0). All 73 entry modules link, and the static import
      graph has no cycle.
    - Each of the five modules that defines a type has both registering modules in its import closure.
    - 49 module-level checks on the real modules, including the Relay and Repeater mode handlers, against two host models:
      in-process semantics and the live guest's, ported from their sources. Each fix is also run on revision 5, as the
      negative control. All 14 mutants that each undo one fix are caught.
    - The ring-safe walk's unit test still passes with the revision 6 module.
- **Changed in revision 5** (published as corpus PR #54). Three pack-side problems from a live browser smoke test on
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
  - **Evidence at publication:** static, plus the module-level walk unit test. The browser staging on host r3 came after
    (see revision 6). Static evidence:
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
  - The optional Dynamic Context backend, which waits on the repeated-output API.
  - (The Reroute definition and the F01 connection-layout port, held back until revision 8, are in revision 9.)
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
| `Power Conductor (rgthree)` | tested (scoped) | Opt-in. The tested repair ships here: numeric modes/IDs, explicit labels via `getLabel`, pack-owned group toggles. Revision 5 moved the load path of its grammar (`common/py_parser.js`). On host r3 the grammar loads from the new path and the parser runs. **Host r3 staging (revision 6 R1, revision 7 S5):** it registers with the opt-in on, Run fetches both WASM files and executes, and a reload restores the node. Blocked on host r3: its code box needs the mounted widget's value handle, which the guest does not pass (R6-4). |
| `Image Resize (rgthree)` | tested (scoped) | Backend native cases: 150/150 equal the original. That is 10 sizes × 5 scaling methods × 3 fit modes, compared tensor-for-tensor with current Core's scaling. No custom frontend. |
| `Lora Loader Stack (rgthree)` | tested (scoped) | Fixed in revision 2: exact-name resolution (the previous v2 fuzzy-matched names) and an input validator. Backend native cases: 8/8 equal the original. Validator checks: 21/21, run in the Guest. One accepted difference, listed below. No custom frontend. |
| `SDXL Empty Latent Image (rgthree)` | tested (scoped) | Fixed in revision 2: the latent carries `downscale_ratio_spacial` like the original. Backend native cases: 72/72 equal the original. No custom frontend. |
| `Any Switch (rgthree)` | converted, partly tested | Backend native cases pass. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Display Any (rgthree)` | converted, partly tested | Backend native cases pass; the F14 serialization fix ships here. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. An own-node PNG metadata candidate passed separately and is not in this revision. |
| `Display Int (rgthree)` | converted, partly tested | Backend native cases pass; F14 ships here. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Fast Groups Bypasser (rgthree)` | converted, partly tested | Tested repair ships here (row state, graph-scoped identities, saved filters). F10 fit-group navigation is open. |
| `Fast Groups Muter (rgthree)` | converted, partly tested | Tested repair ships here. F10 is open. |
| `Image Inset Crop (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Image or Latent Size (rgthree)` | converted, partly tested | Backend native cases pass; its frontend JS is untested. |
| `Label (rgthree)` | tested (scoped) | Frontend-only. **Scope:** browser on live host stack r3 (host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`). **Dialog edits:** 9/9 persist on Classic and on Vue, on live bytes after the focus fix (live 2026-10-21 03:26Z). Each value shows in the dialog, persists to the node, and survives reopen and save/reload. This was measured with revision 4's `label.js`; the dialog path has changed since only by `refresh`'s optional title argument. **Title refresh:** revision 7 staging S1, by byte overlay, Classic renderer. A rename in the title editor redraws and resizes the Label (79×12 → 155×12; a fresh Label 79×12 → 183×12), and a two-line title gives a two-line Label. This held on the untouched startup graph and after a workflow load, with 0 packerrors. **Not staged:** the title refresh under Vue. |
| `Power Lora Loader (rgthree)` | converted, partly tested | Backend native cases pass. The tested repair ships here: authored model info, row info actions, stale-request guard. Since revision 2 its LoRA list comes from `comfy.models.list('loras')`. Open: F03, F04, F13. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Power Puter (rgthree)` | converted, partly tested | Backend native cases pass on the bounded evaluator. F03 and F04 are open. |
| `Seed (rgthree)` | converted, partly tested | Backend native cases pass. An own-node PNG metadata candidate passed separately and is not in this revision. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Image Comparer (rgthree)` | converted, partly tested | Backend native cases: 5/6 equal the original, including preview pixels and PNG metadata. With an empty image batch, v2 raises where the original skips; this is open. The comparer widget is untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Power Primitive (rgthree)` | converted, partly tested | Backend native cases pass. Since revision 4 the "Show/Hide Type Selector Widget" entry is two fixed-label items, and a right-click shows exactly the one the original showed; a differential test against the original's label function covers both states and the toggle. "Set type" works. The rest of its frontend is untested. |
| `Bookmark (rgthree)` | converted, untested | Frontend-only; its button-settings repair ships here. F09 (hidden-subgraph navigation) and F11 (keyboard) are open. |
| `Context (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Context Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Context Merge (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Context Merge Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has a fixed label per type. Revision 6 changes this type's label from the original's "Convert To Context Switch" to "Convert To Context Merge", which is the conversion it runs (see *Accepted differences*). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Context Switch (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Context Switch Big (rgthree)` | converted, PARTIAL | Backend native cases pass. Since revision 4 the "Convert To …" menu item has the original's label, fixed per type (differential test against the original). Blocked: link fan-out when a link from this node is dropped on empty canvas (`onUnplacedLink`; F18). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Random Unmuter (rgthree)` | converted, PARTIAL | The tested failed-attempt cleanup repair ships here. Missing: F17 connection policy — the cycle guard's up-front refusal of a link that loops back on itself. Such a ring is now accepted, without crashing. F07 (independent choice per batch item) is open. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Power Prompt (rgthree)` | converted, PARTIAL | Fixed in revision 2: prompt-tag LoRA strengths outside ±100 apply as in the original. Backend native cases: 72/72 equal the original. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). The rest of the frontend is untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Power Prompt - Simple (rgthree)` | converted, PARTIAL | Backend native cases: 16/16 equal the original. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). The rest of the frontend is untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `SDXL Power Prompt - Positive (rgthree)` | converted, PARTIAL | Backend native cases pass, including the revision-2 prompt-tag strength fix. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `SDXL Power Prompt - Simple / Negative (rgthree)` | converted, PARTIAL | Backend native cases: 36/60 equal the original on current Core. In the other 24, the original's sized SDXL encode is broken on current Core and returns no conditioning, while v2 returns the conditioning the original intends; this is an accepted difference, listed below. Missing: F17 connection policy — refusing a link from a disabled output (the output is still drawn grey). F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Fast Actions Button (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F11 is open. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Fast Bypasser (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Fast Muter (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing). Otherwise untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Mute / Bypass Relay (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), refusing the same node on a second input, and keeping its output to a Mute / Bypass Repeater. Its mode handler resolves the changed node again, because host r3's `onNodeChanged` event carries a copy without methods; revision 6's version did nothing on host r3 (staging R7/R7b). Revision 7 fixes it and takes the new mode from the event. **Host r3 staging, revision 7 S3:** a Relay with nothing wired in drives its Repeater and the KSampler behind it, 0 → 2 → 0. Its mode when driven by its inputs lags on host r3 (stale copies, R6-13). Otherwise untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Mute / Bypass Repeater (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), refusing the same node on a second input, and its output only to the node types that read it. Its two Relay rules still hold after the fact: a Relay input is disconnected again while a toggler is on its output, and its output slot is removed while a Relay drives it. Its mode handler resolves the changed node again, because host r3's `onNodeChanged` event carries a copy without methods; revision 6's version did nothing on host r3 (staging R7/R7b). Revision 7 fixes it and takes the new mode from the event. **Host r3 staging, revision 7 S2:** the wired KSampler follows 0 → 2 → 0 → 4, whether it was added after load or was in the loaded workflow. Otherwise untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Node Collector (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), and refusing the same node on a second input (also through a reroute). Otherwise untested. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Node Combiner (rgthree)` | converted, PARTIAL | Frontend-only. Loads and constructs in the sandbox since revision 3. Missing: F17 connection policy — the cycle guard's up-front refusal (a ring is now accepted, without crashing), and refusing the same node on a second input (also through a reroute). Since revision 6, "‼️ Update to Node Collector" rebuilds the node with `graph.replace`. Revision 5's version would not finish on host r3. **Host r3 staging (revision 6 R5, revision 7 S5):** the upgrade keeps the position, the order of the 3 inputs, the 2 outgoing links and the title, and one Ctrl+Z restores the Combiner. Otherwise untested. Legacy node. F01 expanded layouts are ported (revision 9 R2); collapsed title-edge sockets are PARTIAL pending an approved API or separate critical-pack shim; untested in a browser. |
| `Reroute (rgthree)` | converted, PARTIAL | Frontend-only. Defined since revision 9 (`web/comfyui/reroute.js`, from the consumer `3bed5217`): a pass-through that resolves to its input, type and slot-colour propagation down chains, the four-sided layout with S04's compact sizing and resize side flips, rotate, flip, static sizes, the label toggle and "Clone New Reroute". Missing: F05 (inserting a reroute during an unfinished link drag), F06 per-link colour, and F17 connection policy (the loop guard; a ring is accepted, and the walks stop at visited nodes). The low-zoom label rule needs the host geometry relay (L2); on host r3 the label is drawn at every zoom. Module-tested only; not yet in a browser. |
| `Dynamic Context (rgthree)` | pending capability | Opt-in, disabled upstream by default. Needs a public repeated-output API (F02); a runtime test of that candidate is approved. Missing: F17 connection policy — refusing another Dynamic Context's context output on a non-base input. |
| `Dynamic Context Switch (rgthree)` | pending capability | Same as Dynamic Context. |

### Re-derived in revision 8: every row

**Rule:** a row moves only if passing evidence covers every open item it lists.

**Evidence:** `validation/20261022-rgthree-browser-staging-r5-r7/`:
- r5 = revision 5 rows 1-11 and 8b;
- r6 = revision 6 R1-R9;
- r7 = revision 7 S1-S5.

**Setup:** every run used live host stack r3 (`63d9437e` / `c6b97a15` / `fca402c9`), a byte overlay and the Classic
renderer. "Constructs" means r5 row 6: all 36 registered types construct and stay on the canvas, with 0 page errors.

| Node id | Revision 7 | Revision 8 | Host r3 staging | Why it stays |
| --- | --- | --- | --- | --- |
| `KSampler Config (rgthree)` | tested (scoped) | tested (scoped) | Constructs | — |
| `Power Conductor (rgthree)` | tested (scoped) | tested (scoped) | Registers with the opt-in on, runs, survives a reload (r6 R1, r7 S5) | Stays; its code box is blocked on R6-4 (platform) |
| `Image Resize (rgthree)` | tested (scoped) | tested (scoped) | Constructs | — |
| `Lora Loader Stack (rgthree)` | tested (scoped) | tested (scoped) | Constructs | — |
| `SDXL Empty Latent Image (rgthree)` | tested (scoped) | tested (scoped) | Constructs | — |
| `Any Switch (rgthree)` | converted, partly tested | converted, partly tested | Constructs | F01 |
| `Display Any (rgthree)` | converted, partly tested | converted, partly tested | Constructs; its output box is blocked on R6-4 | F01 |
| `Display Int (rgthree)` | converted, partly tested | converted, partly tested | Constructs | F01 |
| `Fast Groups Bypasser (rgthree)` | converted, partly tested | converted, partly tested | Constructs | F10; the colour-name filter needs R6-9 |
| `Fast Groups Muter (rgthree)` | converted, partly tested | converted, partly tested | Constructs | F10; R6-9 |
| `Image Inset Crop (rgthree)` | converted, partly tested | converted, partly tested | Constructs | No row exercised its frontend: the step switch and "Reset Crop" |
| `Image or Latent Size (rgthree)` | converted, partly tested | converted, partly tested | Constructs | No row exercised its `onConfigured` input retype |
| `Label (rgthree)` | converted, partly tested | **tested (scoped)** | Dialog edits 9/9 Classic and Vue on live bytes; title refresh redraws and resizes (r7 S1, both graph variants) | — |
| `Power Lora Loader (rgthree)` | converted, partly tested | converted, partly tested | Constructs; rows need R6-5 and pickers R6-7 | F01, F03, F04, F13 |
| `Power Puter (rgthree)` | converted, partly tested | converted, partly tested | Constructs; code box R6-4, chips R6-5 and R6-7 | F03, F04 |
| `Seed (rgthree)` | converted, partly tested | converted, partly tested | Constructs; clamp R6-6, last-seed box R6-4 | F01 |
| `Image Comparer (rgthree)` | converted, partly tested | converted, partly tested | Constructs; its canvas needs R6-5 | Empty batch; comparer widget untested; F01 |
| `Power Primitive (rgthree)` | converted, partly tested | converted, partly tested | Type-selector menu and "Set type" (r5 7); the multiline value needs R6-4 | The rest of its frontend is untested |
| `Bookmark (rgthree)` | converted, untested | converted, untested | Constructs; every-node menu items (r6 R2) | F09, F11; its own behaviour was not exercised |
| `Context (rgthree)` | converted, PARTIAL | converted, PARTIAL | One "Convert To …" item (r5 7); F18 notice (r5 5) | F18, F01 |
| `Context Big (rgthree)` | converted, PARTIAL | converted, PARTIAL | As Context | F18, F01 |
| `Context Merge (rgthree)` | converted, PARTIAL | converted, PARTIAL | As Context; converts both ways with Merge Big (r6 R6) | F18, F01 |
| `Context Merge Big (rgthree)` | converted, PARTIAL | converted, PARTIAL | As Context; "Convert To Context Merge" (r6 R6) | F18, F01 |
| `Context Switch (rgthree)` | converted, PARTIAL | converted, PARTIAL | As Context | F18, F01 |
| `Context Switch Big (rgthree)` | converted, PARTIAL | converted, PARTIAL | As Context | F18, F01 |
| `Random Unmuter (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs | F17, F07, F01 |
| `Power Prompt (rgthree)` | converted, PARTIAL | converted, PARTIAL | MODEL output links and keeps its colour (r5 8) | F17, F01 |
| `Power Prompt - Simple (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs | F17, F01 |
| `SDXL Power Prompt - Positive (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs | F17, F01 |
| `SDXL Power Prompt - Simple / Negative (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs | F17, F01 |
| `Fast Actions Button (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs | F17, F01, F11 |
| `Fast Bypasser (rgthree)` | converted, PARTIAL | converted, PARTIAL | Constructs; ring-safe walk (r5 8b) | F17, F01 |
| `Fast Muter (rgthree)` | converted, PARTIAL | converted, PARTIAL | Loop link kept (r5 8); rings and the toggle (r5 8b); Queue items (r6 R2) | F17, F01; toggle state needs R6-13 |
| `Mute / Bypass Relay (rgthree)` | converted, PARTIAL | converted, PARTIAL | Mode handler (r7 S3) | F17, F01; input-driven mode needs R6-13 |
| `Mute / Bypass Repeater (rgthree)` | converted, PARTIAL | converted, PARTIAL | Mode handler (r7 S2) | F17, F01 |
| `Node Collector (rgthree)` | converted, PARTIAL | converted, PARTIAL | Ring-safe walk (r5 8b); upgrade target (r6 R5, r7 S5) | F17, F01; input names need R6-13 |
| `Node Combiner (rgthree)` | converted, PARTIAL | converted, PARTIAL | Upgrade to Collector (r6 R5, r7 S5) | F17, F01 |
| `Reroute (rgthree)` | missing | missing | — | Not in this revision |
| `Dynamic Context (rgthree)` | pending capability | pending capability | — | F02 |
| `Dynamic Context Switch (rgthree)` | pending capability | pending capability | — | F02 |

**Counts:**
- tested (scoped): 5 → 6;
- converted, untested or partly tested: 14 → 13;
- partial or missing: 21 → 21.

**Revision 9** moves one row: Reroute, from missing to converted, PARTIAL. Partial or pending stays 21: 19 PARTIAL
(was 18) and 2 pending (was 3 missing or pending). 38 of 40 node IDs are converted.

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
- **Context Merge Big's menu label** (revision 6). The original labels the item "Convert To Context Switch"
  (`src_web/comfyui/context.ts:418`), but it converts the node to Context Merge. Every other Context type's item names its
  own big or small form. v2 labels it "Convert To Context Merge"; the conversion is unchanged.

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
| Connection filtering: the cycle guard's up-front refusal ("time paradox"; a ring is now accepted, and the link walk is ring-safe) and per-node connection rules (the Repeater's two Relay rules still apply after the fact) | Missing: F17 connection policy (`setConnectionPolicy` / `SlotPatch.linkable`), a policy the host can evaluate without a synchronous worker call. Not registered. | Fast Muter, Fast Bypasser, Node Collector, Node Combiner, Mute / Bypass Repeater, Mute / Bypass Relay, Fast Actions Button, Random Unmuter, Reroute (revision 9; `rerouteConnectionRule`); Dynamic Context (opt-in) |
| Refusing links from disabled outputs | Missing: F17 connection policy, as above. Not registered. | Power Prompt, Power Prompt - Simple, SDXL Power Prompt - Positive, SDXL Power Prompt - Simple / Negative |
| Link fan-out when a link is dropped on empty canvas | A host-owned unplaced-link contribution (F18) | the six Context nodes |
| Dropping a workflow or image onto a node to import its values | A host node-drop contribution (F19) | all node types (pack feature) |
| Progress bar: queue size and interruption updates | Sandbox subscriptions for the published `queue.onPendingChanged` and `queue.onInterrupted` (F20) | rgthree progress bar |

The published API declares the following, and the live sandbox guest (`c6b97a15`) does not provide it yet. Each was found
in the browser staging of revision 5 or in the static live-readiness audit. Platform requests are filed; the pack code
follows the published API and needs no change when the guest catches up.

| Behaviour on host r3 | Needs (published API) | Nodes |
| --- | --- | --- |
| A mounted widget's stored value: the code and text boxes render no value | `MountDef.render(container, value)` with `MountedValue`, and `defaultValue` / `serialize` honoured | Power Conductor, Power Puter, Power Primitive (multiline value), Display Any, Display Int, Seed (last-seed box) |
| A canvas widget's handle, palette and value: setting its height, reading its value, drawing in theme colours | `CanvasHandle.widget`; `CanvasDef.draw(context, size, theme, value)` | Power Lora Loader rows, Power Puter output chips, Image Comparer |
| Correcting a property as it is edited (clamping, normalising) | `PropertyChangeEvent.setValue` / `reject` | Seed (`randomMax`, `randomMin`), Fast Actions Button (shortcut key) |
| Menus a pack raises itself (pickers, row menus, the rgthree menu) | `comfy.ui.showMenu` with `run` callbacks kept in the worker | Power Lora Loader, Power Puter, rgthree menu, Bookmarks button |
| Filtering groups by a colour name (hex codes work) | A synchronous `comfy.defs.nodeColor` | Fast Groups Muter, Fast Groups Bypasser |

Revision 6 works around four more such gaps, as described above: the `onNodeChanged` node, a stored setting read at
load, `queue.run` with handles, and an unconfirmed node from `graph.add`.

### Host behaviour and remaining revision 9 R2 gaps

The original draft's historical real-guest runs used host r3 (`63d9437e` / `c6b97a15`), r4a r2 (`16924bbe`) and
a candidate with geometry relay L2. Those runs are not R2 browser or real-guest acceptance. R2 removes the
unpublished collapsed-socket dependency on every host; the Reroute source and its existing fallbacks are unchanged.

| Node | R2 behaviour on host r3 (and r4a r2) | Missing | With an approved geometry relay L2 |
| --- | --- | --- | --- |
| The 24 F01 types | Expanded layouts, collapse grouping, labels and greying use the published contract. Whole-node collapsed title-edge socket geometry is PARTIAL; no collapsed-socket field is read or written. | MIKE-published general API or a separately reviewed critical-pack shim | Still partial; L2 does not supply this authority |
| The 24 F01 types | During a load or after a layout change, a hook can carry a node snapshot the host took before the pack's own slot writes arrived. `position` and `direction` may then be sent once more; this settles on the next pass. | (guest replica timing; historical draft evidence) | Same |
| Reroute | The label is drawn at every zoom (the original hides it below 0.6), and nothing subscribes to `onViewportChanged`. No error. | L2 (`getBounds`, `getScreenRect`, coalesced `onViewportChanged`) | The original's rule, exact at 0.6 |
| Reroute | On r3, `defs.typeColor` and `isTypeCompatible` answer a message later. The colour patch and the disconnect of an incompatible target follow when the answer arrives. r4a's colour tables (R6-9) answer at once. | Synchronous answers (r4a R6-9) | — |
| Reroute | A chain into a widget input forwards the target's own declaration, not the merged one. | `InputSlotHandle.mergeWidgetConfig` in the guest | — |
| Reroute | "Clone New Reroute": the clone is wired and selected once the host confirms it (polled, up to about 2 s). | Synchronous confirmation of `graph.add` | — |
| Reroute | Rings are accepted (no loop guard). | F17 | F17 |

## Pending items (not yet supported)

- F01 (partial): whole-node collapsed title-edge socket geometry for all 24 layout types. It needs a MIKE-published
  general API or a separate critical-pack shim; the draft's unapproved field and L1 relay are not an API dependency.
- F02 — repeated (dynamic) outputs for the opt-in Dynamic Context nodes.
- F03 — model metadata provider: trained words, Civitai details and images.
- F04 — same-user JS↔Python model-info storage continuity.
- F05 — Reroute insertion/reposition during an unfinished link drag.
- F06 — remaining Reroute presentation parity: per-link colour. (The low-zoom label rule is in revision 9 and needs
  the host geometry relay, L2.)
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
  - Reroute's loop guard is kept, unregistered, as `rerouteConnectionRule` (revision 9).
- F18 — host-owned contribution for links dropped on empty canvas (replaces `onUnplacedLink`).
- F19 — host node-drop contribution (replaces `onDragOver`/`onDrop`).
- F20 — sandbox subscriptions for `queue.onPendingChanged` and `queue.onInterrupted`.
- Power Prompt LoRA and embedding insert combos when the model list exceeds the worker's definition bounds
  (needs a public model-catalogue read).

## Open test gates

- Revision 9 R2's browser checks: expanded F01 layouts, the unchanged Reroute conversion and the production
  regressions. The original packet's `BROWSER_SMOKE_PLAN.md` is historical; its collapsed-socket/L1 rows are held
  until an API is published or a separate shim is approved. G01–G10 still need the published geometry relay L2.
- Host renderer prerequisites S01–S04: historical frontend changes require verification against an approved host
  successor. The unapproved S02 collapsedPosition surface and L1 relay must not be treated as pack API.
- Backend native cases running inside the Guest (sandboxed), and Core prompt validation at runtime for the Lora Loader Stack
  validator. Its checks pass structurally and in the Guest.
- Image Comparer with an empty image batch.
- Original-comparison runs for the eight frontend-only nodes listed as untested.
- Label's title refresh under Vue. It was staged on Classic only.
- The browser staging of revisions 5-7 on host r3 is done, and revision 7's gate passed (S1, S2, S3, S5). The
  evidence is in `validation/20261022-rgthree-browser-staging-r5-r7/`. It is overlay staging, not a release: the registry update and a frontend catalogue refresh
  are still to do.
- gVisor admission and whole-pack acceptance review.

## Authority and permissions

- No SDK permissions (12 nodes): the Context family, Any Switch, Display Int, KSampler Config, Seed, Power Prompt - Simple,
  SDXL Power Prompt - Simple / Negative.
- `assets` (4): Lora Loader Stack, Power Lora Loader, Power Prompt, SDXL Power Prompt - Positive.
- `raw` (7): Display Any, Image Inset Crop, Image Resize, Image or Latent Size, Power Primitive, Power Puter, SDXL Empty Latent Image.
- `ui` (1): Image Comparer.
- Frontend: `web_directory` is `web`, served at `/extensions/rgthree-comfy/`. Each of its 74 `.js` files is an entry
  module of the sandboxed pack worker (73 until revision 8; revision 9 adds `comfyui/connection_layout.js`). No static directories and no pack HTTP routes.
  Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. LoRAs, checkpoints, CLIP and embeddings come from the user's managed model catalogue.
