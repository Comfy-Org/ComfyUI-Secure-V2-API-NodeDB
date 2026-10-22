# rgthree-comfy rev 7 (r2): browser staging results (BART, 2026-10-22, 01:10–01:19Z)

**Verdict: GATE PASS.** S1, S2, S3 and S5 all pass. S4 is recorded, as the plan asks.
- Per the plan, the node counts may now move off rev 4's.
- Power Conductor keeps "tested (scoped)", with its code box recorded as blocked on R6-4.
- A live release still needs the registry update (operator, per Ben) and a frontend catalogue refresh. I've done neither.

## Setup
- **Mode B overlay**, session-only; nothing installed or deployed.
- **Packet:** zip `0608b48f…`, forward-slash paths, with top folder `rgthree-rev7-staging-packet-20261022/`.
  `SHA256SUMS` is `d441695b…`; all 88 entries verified, 83 served files. 4 modules changed from rev6, as stated.
- **Host, checked on every load:** host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`. Every served
  response was sha-checked: 0 mismatches, 0 non-200.
- **Graph handling, per the plan:**
  - Nothing calls `app.graph.clear()`. An empty canvas is an empty workflow loaded with `app.loadGraphData`.
  - The untouched-graph variant only moves the viewport; it loads nothing.
  - Before every key press, the rgthree worker's `comfy.graph.id` (that worker's `self.comfy.graph.id`) was logged next
    to `app.graph.id`. **They were equal before every press.**
- **Writes:** the only blocked request per load was `POST /api/settings`, from dismissing the release-notes popup.
  `POST /api/prompt` (R3) was answered in the browser, recording `extra_data` key names only.
- **Loads (9 in all):** `runs/r7-*`, all on a fresh browser context.
  - `r7-s123-untouched` and `r7-s123-loaded` are superseded by their `-b` re-runs. In the first pair, S2's Repeater sat
    at graph y=60, so its title was under the app's floating toolbar. My click hit the toolbar, nothing was selected and
    Ctrl+M did nothing: the Repeater's own mode stayed 0. Even in that pair, the optional pre-loaded KSampler (Repeater
    placed lower) and S3 worked. In the `-b` runs, every clicked title sits at graph y ≥ 150.

## Rows
| # | Verdict | Evidence (both variants: untouched startup graph / after a workflow load) |
| --- | --- | --- |
| S1 (R4) | **PASS** | **First Label, renamed in the title editor to "A longer label text for staging":** the canvas draws the new text (`S1-first.png`), the size goes 79×12 → 155×12, and the pixels in the node's bounds change. **A fresh Label** → "Fresh label renamed to longer text": 79×12 → 183×12, redrawn. 0 packerrors. **Two-line text:** this frontend's title editor is a single-line `<input>`, and Shift+Enter commits it, so no line break can be typed. Instead, as an extra recorded check, a two-line title set on the host node gave a two-line Label: 155×24, redrawn (`S1-two-line-host.png`). |
| S2 (R7) | **PASS** | A KSampler added after load, wired into a Repeater. Ctrl+M, Ctrl+M, Ctrl+B on the Repeater: the KSampler goes **0 → 2 → 0 → 4**, with the Repeater the same. 0 packerrors. **Optional run** (loaded variant), with a KSampler that was already in the loaded workflow: **0 → 2 → 0**. |
| S3 (R7b) | **PASS** | Relay → Repeater (nothing into the Relay), with a KSampler into the Repeater. Ctrl+M twice on the Relay: [Relay, Repeater, KSampler] go **[0,0,0] → [2,2,2] → [0,0,0]**. 0 packerrors. |
| S4 | recorded | **Group made with Ctrl+G** around PreviewImage, KSampler and Fast Muter. **(a), no pre-selection:** PreviewImage shows "Queue Selected" only; KSampler shows neither item. **(b), PreviewImage pre-selected:** the right-click on the Fast Muter selects it, and it shows neither item. No "visibility not yet computed … showing it" line appeared. "Queue Selected" behaves as the pack intends: shown in (a) on the PreviewImage, not in (b). **"Queue Group" is hidden on all three, with no fallback line**, which matches the R6-12 case: the structure replica is empty. Worker and page graph ids were equal. |
| S5 | **PASS** | **R1:** registered 32 ms after graph-ready; constructs; Run fetches both WASM files (200, sha OK) and executes; reload restores the node as itself. **R2:** 0 late-extend errors for the 13 rgthree types on all 9 loads; other packs' residue 0–2. **R3:** one POST per use, via the menu and via the command. **R5:** wiring, position and title "Mine" correct, rAF under 50 ms, one Ctrl+Z restores the Combiner, and the expected "dropped 2 link(s)" host warning. **R9, every load:** 0 module-load failures, 0 refusal rows, exactly 8 notices, 0 DataCloneError. |

## Evidence
- **Harness:** `harness/rev7-stage.mjs`, built from rev6-stage.mjs. Stages: s123-untouched, s123-loaded, s4, s5-rows,
  pc-on.
- **Per load:** `runs/r7-*/RESULT.json`.
- **Screenshots:** `S1-first.png`, `S1-fresh.png`, `S1-two-line-host.png`, `S123-*.png`, `S4-menus.png`,
  `R1-pc-run.png`, `R1-pc-after-reload.png`, `R5-after-upgrade.png`.
