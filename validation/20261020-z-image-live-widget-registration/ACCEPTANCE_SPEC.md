# Z-Image Power Nodes: live browser acceptance spec (short), r1

> **EXPECTED TO FAIL ON LIVE until the `defineWidgetType` bridge (guest half + host bridge) ships.**
> This is platform request #11. Run on today's live stack, check 0 fails for
> every listed input. That is the platform gap, not a pack bug. The spec doubles as the bridge's regression test.

NED, 2026-10-20, for MERVYN (decision m_6403475f76). This is a spec only: no Playwright source and no run. BART runs it via JERRY.

**Target:**
- Pack `z-image-power-nodes`, key `xc6c3f11`, rev 2 `v2/`, as on corpus main `b52a2b89` (unchanged since `d6271b5c`).
- Live host-stack r3: guest.mjs `c6b97a15…` and host-entry.mjs `63d9437e…`.

**Scope:** UI only, so no model, GPU or image generation is needed.
- Sampler and encoder nodes are only added and serialized; they are never queued.
- The only real queue runs (section C) execute three text nodes on the CPU.

**Evidence base:**
- `ZIPN_CENSUS.json`: every input of the six custom types, from `v2/secure-nodes.json`.
- `LIVE_SOURCE_FACTS_COMPACT.json`: line references in the live guest and host.

## Setup and records (every check)

- Use a fresh browser profile on the live public frontend. Load the pack, then start each check on an empty workflow.
- Record:
  - the frontend version;
  - the sha256 of the guest.mjs and host-entry.mjs actually served;
  - host-page and worker console output;
  - every `POST /prompt` body and its response.
- If the served hashes differ from the target, say so. The bridge may have shipped.
- "Serialized" means the frontend's own prompt serialization. Call it in the page (`app.graphToPrompt()`) without posting, and read `output[<node id>].inputs`.
- "Idle" means 2 s after the last widget or worker message for the node.
- No retries: a failed row is recorded as it is.

## A. Check 0: the six widget types register (gate, all 18 blocked nodes)

For each node below:
1. Add it to the canvas.
2. Leave its non-ZIPN inputs unlinked.
3. Wait for idle.
4. For **every ZIPN input listed**, check:

- **0a.** The node has a widget with that name. Any input slot of that name is bound to the widget (a widget input), not a plain socket of type `ZIPN_*`. Separators have no slot (the original is socketless).
- **0b.** The serialized inputs contain that key, with the value the original serializes:
  - separators and gallery buttons: `null`;
  - predefined style/palette: the selected item name, or `null` before the catalogue loads, as in the original;
  - user-input combos: the selected string.
- **0c.** The value can be changed through the widget, and the serialized value follows the change. Use the first that applies:
  - predefined galleries: the `Next <name>` button;
  - user-input combos: pick another option in `select[aria-label=<name>]`;
  - separators: not applicable.
- **0d.** No host or worker error mentions `defineWidgetType`, `DataCloneError` or a rejected registration.

| Node (`… //ZImagePowerNodes`) | Report class | ZIPN inputs (all required) |
| --- | --- | --- |
| ZSamplerTurbo | partly tested | divider (separator, divider) |
| ZSamplerTurboAdvanced | partly tested | divider (separator, divider) |
| ZSamplerTurbo2Laboratory | partly tested | divider1-4 (separator, divider) |
| StylePromptEncoder2 | partly tested | gallery (gallery button), spacer (separator, spacer) |
| StyleStringInjector2 | partly tested | gallery (gallery button) |
| MyTop10Styles | partly tested | divider (separator, divider) |
| MyTop10StylesEditor | partly tested | gallery_1-10 (gallery buttons), spacer_1-9 (separators, spacer) |
| ZSamplerTurbo2Simple | tested (scoped) | divider |
| ZSamplerTurbo2 | tested (scoped) | divider, divider2 |
| ZSamplerTurbo2Advanced | tested (scoped) | divider, divider2 |
| ZSamplerTurboX21 | tested (scoped) | divider1 |
| ImageFilter | tested (scoped) | divider1 (divider), divider2-3 (spacer) |
| ImageLabeler2 | tested (scoped) | divider1 |
| StyleLibraryV10 | tested (scoped) | style (ZIPN_PREDEFINED_STYLE) |
| PaletteLibraryV20 | tested (scoped) | palette (ZIPN_PREDEFINED_PALETTE; optional unset, so required) |
| StylePromptEncoderX21 | tested (scoped) | style (ZIPN_PREDEFINED_STYLE), palette (ZIPN_PREDEFINED_PALETTE) |
| StylePromptEncoderX22Advanced | tested (scoped) | style (ZIPN_STYLE ← user_styles), palette (ZIPN_PALETTE ← user_palettes) |
| CustomStylePromptEncoderX21 | tested (scoped) | custom_style (ZIPN_STYLE ← custom_styles). Its `palette` is optional with force_input, a socket by design, and is not checked. |

**Expected on today's live stack: FAIL** for every input above.
- Each one shows as an unlinked `ZIPN_*` socket with no widget.
- The key is missing from the serialized inputs.
- A queued graph in which one of these nodes feeds an output is rejected (HTTP 400), with `required_input_missing` on each required ZIPN input.
- The guest rejects the registration with a DataCloneError from the generic RPC proxy.

The other 13 nodes have no ZIPN input and are not part of this spec.

## B. UI checks for the 7 open nodes (run after check 0 passes for the node)

The original column is pristine `c6c3f11`. The expected column is rev 2 `v2/` (file references are under `v2/js/widgets/public/`).

| Widget | Original | Expected from the conversion | PASS criteria |
| --- | --- | --- | --- |
| **B1 Separator** (ZSamplerTurbo, ZSamplerTurboAdvanced, ZSamplerTurbo2Laboratory, StylePromptEncoder2, MyTop10Styles, MyTop10StylesEditor) | Socketless canvas widget, height 20 (or `height`). `divider`: a 1 px solid line from x=10 to width−10 at mid-height, in `NODE_DEFAULT_BOXCOLOR`. `dotted`: 2 px dashed [2,2]. `bold`: 6 px. `spacer`: draws nothing. Serializes `null` (`js/widgets/separator_widget.js`). | The same geometry as SVG (`separator_widget_type.js` `separatorGeometry`). Colour is `var(--comfy-native-node-box-color)`. Serializes `null`. | (1) Widget height 20 ± 1 layout px. (2) `divider`: one visible horizontal line, stroke width 1, from 10 to width−10 (±1 px), vertically centred. (3) `spacer`: nothing visible. (4) Serialized `null`. (5) Saving and reloading the workflow keeps every other widget's value in the same position (`widgets_values` equal before and after). |
| **B2 Style gallery button** (StylePromptEncoder2 `gallery`, StyleStringInjector2 `gallery`, MyTop10StylesEditor `gallery_1-10`) | A full-width button "🖼️  Select Style[ N] ..." under the style combo. Clicking it opens the style gallery with the combo's current style selected. Choosing a card, or Enter on a search, sets the combo **directly above** to `"<Style Name>"` (quoted) and closes the gallery. Escape leaves the combo unchanged. The button serializes `null`. | The same: a button with aria-label `Select Style[ N]`. The gallery opens through `comfy.ui.showDialog`, with search input `#zipn-search-input` and cards `#zipn-element-<idx>` (`style_gallery_button_widget_type.js`, `public_gallery_dialog.js`). | (1) Click: the gallery is visible within 5 s with at least 1 card. (2) Type `Vintage Photo` and press Enter: the gallery closes. The combo above and its serialized value equal the first search result's name, quoted (expected `"Vintage Photo"`). (3) Reopen, click a different card: the combo takes that card's name. (4) Reopen, press Escape: the combo is unchanged. (5) The button serializes `null`. (6) Editor only: each `gallery_N` changes `style_N` and no other combo. |
| **B3 Top-10 labels and selection** (MyTop10Styles with MyTop10StylesEditor) | The selector's `style_1-10` toggles read `N - <name>` for each valid editor style (not empty, `-` or `none`), otherwise `-`. Changing an editor combo relabels linked selectors. Turning one toggle on turns the others off. Chained selectors (`output` → `input`) on the same `output_to` channel deselect each other (`js/my_top_styles.js`). | The same (`top_styles_frontend.js`). | Link editor `TOP_STYLES` to selector `top_styles`, then set editor `style_1` = `"Phone Photo"`, `style_2` = `"Casual Photo"` and the rest `none`. (1) Labels are exactly `1 - "Phone Photo"`, `2 - "Casual Photo"`, then `-` ×8. (2) Change `style_2` to `none`: label 2 becomes `-`. (3) With `style_1` on, turning `style_2` on turns `style_1` off. (4) Two chained selectors on `custom_1`: turning one on turns the other off. With the second on `custom_2`, nothing changes. |

### Known failure points that remain after the bridge ships (predicted from source; record them, don't work around them)

- **B1 line.** The line's end point comes from `ResizeObserver`, and the live worker's observer is inert (guest.mjs:382-386). With no width reported, the line stays hidden (`separator_widget_type.js:65`). Expect `divider` to show blank space of the right height unless the bridge or facade delivers the container size. `spacer` is unaffected.
- **B2 card click.** The card click handler calls `closest()` on the event target, and the live facade stubs `closest`, `querySelector` and `focus` (guest.mjs:203-213). Mouse selection (B2.3) is expected to fail. The keyboard path (B2.2: search plus Enter selects the first result) does not depend on them. Record each path separately.
- Both are already listed in `zimage-completion-20261016/FROZEN.md` (inert ResizeObserver, empty `querySelector`, no focus or scrollIntoView). Its unverified candidate pack edits target them. A pack fix is a new revision and would need its own run.

## C. Top-10 "next" through `comfy.queue.onAfterRun` (real queue, text nodes only)

**Graph:** MyTop10StylesEditor (B3 setup) → MyTop10Styles, with `style_1` on, `control_after_generate` = `next` and `output_to` = `custom_1`. MyTop10Styles `output` → a core output node that accepts STRING (e.g. `PreviewAny`; record which one).

**What is read:**
- **Submitted:** the selector's `style_N` booleans in each `POST /prompt` body.
- **Final:** the selector's toggles after the Run has settled (no change for 5 s).

| Case | How | Original (submitted → final) | Expected v2 (PASS = exactly this) |
| --- | --- | --- | --- |
| C1 fixed | `control_after_generate` = `fixed`, one Run | [1] → 1 | [1] → 1 |
| C2 single run | `next`, one Run, batch 1 | [1] → 2 | [1] → 2 |
| C3 two runs | `next`, two Runs, batch 1, the second after the first has settled | [1], [2] → 1 | [1], [2] → 1 |
| C4 rejected | `next`. Disconnect the output node's input so the only output fails validation (HTTP 400) | [1] refused → 1 | [1] refused → 1 (no advance) |
| C5 batch 2 | `next`, one Run, batch count 2 | [1][2] → 1 | **[1][1] → 1**: the accepted difference (report, "Pending capabilities"). Any other result fails. |

**PASS also requires:**
- every accepted prompt returns 200;
- C4 returns 400 for the output node only, and never `required_input_missing` on `divider` or a gallery input;
- no host or worker error.

The source of these rows is the rev-2 controller differential (report table). This run replaces its fakes with the real queue.

## D. Classes on PASS (counts unchanged until then)

- **Check 0 PASS for all 11 tested nodes:** the label "backend only; live UI blocked" is removed from each. They stay tested (scoped), and the count is unchanged.
- **An open node moves from "converted, partly tested" to "tested (scoped)"** only when check 0 and all of its rows pass:

| Node | Rows required |
| --- | --- |
| ZSamplerTurbo | 0, B1 |
| ZSamplerTurboAdvanced | 0, B1 |
| ZSamplerTurbo2Laboratory | 0, B1 |
| StylePromptEncoder2 | 0, B1 (spacer), B2 |
| StyleStringInjector2 | 0, B2 |
| MyTop10StylesEditor | 0, B1 (spacer), B2 (all 10), B3 |
| MyTop10Styles | 0, B1 (divider), B3, C1-C5 |

- **If everything passes:** 31 tested (scoped), 0 partly tested. C5 stays a documented accepted difference.
- **A failed row** keeps its node where it is, with the row named in the report.
- **If only the B1 line fails** (the inert-observer risk above): ZSamplerTurbo, ZSamplerTurboAdvanced, ZSamplerTurbo2Laboratory and MyTop10Styles stay partly tested. StylePromptEncoder2 and the editor, whose separators are spacers, are not held back by it.

## E. Model and GPU

None needed:
- Sampler, encoder and loader nodes are added and serialized only. Their `MODEL`/`CLIP`/`CONDITIONING`/`LATENT` inputs stay unlinked, and they are never queued.
- Section C runs only MyTop10StylesEditor, MyTop10Styles and a core text output node, on the CPU.
- The gallery needs the pack's two declared routes and the static sample images, but no model.
