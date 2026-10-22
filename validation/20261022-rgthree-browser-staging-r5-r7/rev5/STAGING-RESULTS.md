# rgthree-comfy rev 5 (candidate r2): browser staging results (BART, 2026-10-21)

**Verdict: not a full PASS.** Row 9 (required) FAILS on the live host-stack r3. Every other row passes. Two findings
(F-1, F-2) need MERVYN's attention even where their rows pass. Per the plan, the node counts in `SECURE_CONVERSION.md`
stay at revision 4's.

## Setup
- **Mode B ("overlay").** Session-only Playwright routes; nothing was installed or deployed, so there is nothing to
  restore.
  - `/api/extensions`: the live list has 139 entries, 54 of them rgthree. The overlay list has 158 entries, exactly the
    73 rev5 entries among them.
  - `/extensions/rgthree-comfy/<rel>` is served from `served-web/` with the live headers.
  - Every one of the 220 responses per load was sha-checked against `SHA256SUMS`, with 0 mismatches. This stands in for
    preflight 2, which is mode A only.
- **Host, as served (preflight 1 PASS):**
  - `host-entry.mjs`: `63d9437e3213…`
  - `guest.mjs`: `c6b97a154729…`
  - `ui-renderer.mjs`: `fca402c9f8a9…`. This is Label r2, live since 03:26Z. Run 1 ran before the swap, on `bcf7ad64`.
- **Windows (UTC):**

  | Run | Window |
  | --- | --- |
  | run 1, stage1 overlay and baseline | about 03:20 |
  | run 2, default settings | 03:46:02–03:48:43 |
  | Power Conductor load, plan path | 03:50:05–03:50:42 and 03:54:11–03:54:40 |
  | Power Conductor diagnostics | 03:54:40–03:55:30, 03:57:58–03:58:58, 03:59:47–04:01:02 |

- **API writes after sign-in were blocked.** None were attempted, and no dialogs appeared in any load.

## Rows (run 2 default load unless noted)
| # | Verdict | Evidence |
| --- | --- | --- |
| P4 | PASS | 73 rgthree URLs, none under `link_fixer/`, `models/` or `common/components/` |
| 1 | PASS | 0 rgthree module-load failures: no page error naming the prefix, no "Error loading extension", no loaderror, no `[url mode]` or `[source mode]` row. The host's `loadResults` can't be read from the page (a module-scoped `SecureExtensionHost`), so this row is judged from console and page errors. |
| 2 | PASS | 220 requests, all 200, at most 3 per path, 0 `/rgthree/` requests. `common/media/rgthree.svg` fetched once (200). No `.wasm` in the default load. |
| 3 | PASS | The badge reads `Queue: 0`; "Show executing node" and "rgthree-comfy" are both present. The optional queued prompt was not run (no paid work). |
| 4 | PASS | 0 refusal rows, including after the menus in rows 7 and x1 were opened. |
| 5 | PASS | Exactly the 8 expected `[rgthree-comfy]` warnings (6 onUnplacedLink, onDragOver, onDrop) and no other "not available" line. No F20 notice. Same in all 4 loads. |
| 6 | PASS by the row's letter; see F-2 | All 36 expected types are registered (24 backend, 12 frontend). None of Reroute, Power Conductor, Dynamic Context or Dynamic Context Switch is registered. All 36 construct and stay on the canvas through a 6 s settle, with 0 page errors. However, 10 console errors from rgthree hooks fire during construction (F-2). Run 1's "no such node" rows were teardown races from clearing at once; run 2 separates them, with 0 errors after clear. |
| 7 | PASS | **Menu with the selector visible:** exactly "Hide Type Selector Widget". Running it hides the `type` widget. **Menu with the selector hidden:** exactly "Show Type Selector Widget". "Set type" offers exactly STRING/INT/FLOAT/BOOLEAN; INT was applied. Each of the 6 Context types has one "Convert To …". The harness first scored this row false because its case-insensitive regex also matched core's "Convert to Subgraph"; I recounted from the recorded menus. Minor: Context Merge Big's item reads "Convert To Context Switch" but converts to Context Merge (`context.js:31-33`). |
| 8 | PASS | A Fast Muter X→A→X loop is linked and kept, with no alert and 0 console errors. Power Prompt's MODEL output (`#666665`, `opt_model` unconnected) links to KSampler.model and stays `#666665`. |
| 8b | PASS (both rings) | Reroute ring and two-Collector ring. The ring link is accepted and kept. No alert. 0 RangeError or "Maximum call stack" in the console or the 5 workers; an in-worker error/rejection hook was installed in all 5. Page responsive (rAF 3–11 ms). M lists exactly K: widget `1`, "Enable KSampler", which follows the rename to "Enable KSampler renamed". A canvas click on M's toggle sets K's mode 0→2→0. The rename used the title editor; the mode change used Ctrl+M. |
| 9 | **FAIL** | (a) Power Conductor never registers with the opt-in stored `true`. (b) Once registered, it can't take code. (c) The WASM part is fine. Details below. |
| 10 | PASS | Other-pack errors: 1, the same as the live baseline (the Crystools "this pack declares no backend routes" pageerror at startup). Crystools loads 10/10 and KJNodes 26/26 entries, all 200, with no load errors. |
| 11 | PASS | 0 DataCloneError in console, page errors or worker rows, in all loads. |

### Row 9 detail
- **(a) The opt-in gate can't open on r3.**
  - The host returns `true` from all of `app.ui.settings`, comfy v2 and `extensionManager`, yet the type never
    registers.
  - Cause: `power_conductor.js:143` gates `comfy.defs.define` on a synchronous read at import time. On guest
    `c6b97a15`, `settings.declare` seeds the cache with the default, and the stored value arrives later through the
    async `settingsdeclare` reply. The host's own comment there says it "must correct the cache before gates read it".
  - Proof: I delayed only Power Conductor's import fetch by 3 s, with the same bytes, and the type then registers.
- **(b) Once registered, it can't take code.** Its code widget's `render` throws at `power_conductor.js:163` (value
  handle undefined; the F-2 pattern), so no textarea appears. A saved workflow holding the code loads, but the code
  widget is absent afterwards.
- **(c) The WASM half is clean.** Clicking Run fetched `lib/tree-sitter.wasm` and `lib/tree-sitter-python.wasm` (200,
  sha OK). The parser initialised and execute completed: the worker logged `=====` and `value null`. There was no CSP or
  WebAssembly refusal, so there is no host CSP finding.

## Findings
- **F-1: Late `comfy.defs.extend(/./)`.** New with rev5; the live baseline has 0.
  - Each overlay load logs 14–19 `[nodeApi] comfy.defs.extend('X') was called after comfy.defs.define('X'), so it will
    not be applied` errors.
  - They cover 10–12 of the 12 frontend-defined rgthree types. One load also hit KJNodes' GetNode and SetNode, because
    the selector matches every pack. The set varies from load to load, which points to a load-order race.
  - Sources: `comfyui/menu_queue_node.js:87` and `comfyui/feature_import_individual_nodes.js:65`.
  - Impact (observation x1): inside one group, PreviewImage and KSampler show "Queue Selected Output Nodes (rgthree)" and
    "Queue Group Output Nodes (rgthree)"; a Fast Muter shows neither (`x1-fast-muter-menu.png`). Drop-to-import is
    already unavailable in the sandbox, so nothing more is lost there.
- **F-2: rgthree hooks throw against guest c6b97a15's API.** The host catches these and logs them as console errors.
  rev5 appears to expect a newer guest API than r3 serves. The affected nodes construct, but these widgets and
  behaviours don't work on r3:
  - **`mount` `render` gets no value handle** (the guest calls `def.render(container)`):
    - `display_any.js:19` (also on live rev4)
    - `power_primitive.js:36` (the multiline value)
    - `power_conductor.js:163` (the code widget)
  - **`mount` result has no `.widget`:**
    - `utils_widgets.js:189`, via `power_lora_loader.js:675` and `power_puter.js:138`
    - `image_comparer.js:324` (also on live rev4)
  - **`onPropertyChanged` event has no `setValue`:** `seed.js:198` and `:201`; `fast_actions_button.js:291`.
  - **canvas `draw` options have no `theme`:** `utils_canvas.js:55`, via `power_puter.js:261`.
- **F-3: one unexplained harness read.** One `page.evaluate` in the first diagnostic Power Conductor load failed with
  "RangeError: Maximum call stack size exceeded". 30 identical reads in a repro run passed, and no RangeError ever
  reached the console, page errors or workers. Not counted.
- **Known pre-existing defects** (Settings, Star on Github, Convert Reroutes): not clicked, not seen.

## Evidence (under `rgthree-rev5-staging/`)
- **Harnesses:**
  - `harness/rev5-stage.mjs` (run 1, unchanged)
  - `harness/rev5-stage2.mjs` (run 2 and the Power Conductor loads)
  - `harness/summarize.py` (per-row rules)
- **`runs/r2-default-overlay/`:**
  - `RESULT.json` and `SUMMARY.json`
  - `extensions-response.json`
  - screenshots: `topbar.png`, `c6-constructed.png`, `c7-menu-selector-{visible,hidden}.png`, `c7-set-type.png`,
    `c8-loop.png`, `c8-power-prompt-model.png`, `c8b-{reroute,two-collectors}-{ring,k-muted,final}.png`,
    `x1-fast-muter-menu.png`
- **Power Conductor loads:**
  - `runs/r2-pc-overlay/` and `runs/r2-pc-overlay-plain/`: plan path; does not register.
  - `runs/r2-pc-overlay-delay-pc-import{,-b,-c}/`: diagnostics, including `c9-code-entered.png` and
    `c9-after-run.png`.
- **Run 1:** `runs/stage1-{overlay,baseline}/RESULT.json`. The baseline is the live rev4, used for row 10 and for the
  F-1 and F-2 comparisons.
- **Not recorded:** a HAR, because its request headers would carry the session cookie. The JSON network log keeps
  paths, methods, statuses and sha checks only.
