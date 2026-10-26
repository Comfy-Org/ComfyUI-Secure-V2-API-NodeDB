# LoRA Manager rev 10 frontends: browser smoke plan for BART's lane

This checks what the guest fakes cannot: the real host stacks running rev 10's `secure_web/lm_frontends.js`, the one
module that registers on load. MERVYN routes and selects it. Run it only after MERVYN has reviewed rev 10 and built its
stage.

- **Hosts.** Run the "live" column on host-entry `63d9437e`, guest `c6b97a15`, ui-renderer `fca402c9`. Run the
  "with r4a/#11" column once host-stack r4a (the `defineWidgetType` bridge) is available.
- **Setup.** Serve the stage's `v2/secure_web` like the rgthree staging: a Mode B overlay with session-only Playwright
  routes, nothing installed, and each response sha-checked against the stage manifest.
- **Expected module list.** `/api/extensions` lists 46 LoRA Manager modules: main's 40, plus `guest_compat.js`,
  `lm_frontends.js`, `original_layout.js`, `saved_layout_restore.js` (r3), `text_row_sync.js` and `widget_types.js`.

## What changes the expected results

- **r4a/#11 (`defineWidgetType`).**
  - Without it (live), the LORAS, AUTOCOMPLETE_TEXT_LORAS and AUTOCOMPLETE_TEXT_PROMPT inputs stay sockets, and rev 10
    wires nothing for Lora Loader, Lora Stacker or Create Hook LoRA.
  - With it, those inputs become rev 10's widgets.
  - Every step gives the result for both hosts.
- **G6, the r4a allowlist including `comfy.models.list`.** Without it, the rows editor shows the refusal and offers no
  catalogue entries. Typed text still creates rows.
- **G1, no `beforeSerialize` replacement value, on either host.** Save Image sends its filename prefix unexpanded.
- **R6-4, the mount value handle (r4b).** Debug Metadata's panel is not restored from a saved workflow, on either host.
- **Saved widget values (step S12).** Core places `widgets_values` by position (MERVYN's host-stack r4a W1), so the
  original's current-format saves land shifted by one on rev 10's widgets. Rev 10 r2 migrates them by name in
  `onConfigured`, so on r4a they should restore.

## Fixtures

- **The pack's own example workflows**, saved by the original (data only, from `v2/example_workflows/` at main
  a45522ff):
  - `nunchaku-flux.1-dev.json`, older format. Lora Loader `widgets_values` = `[text, rows]`. The Lora Stacker's are
    `["<lora:FLUX.1-Turbo-Alpha:1>", [1 row]]`.
  - `Lora_Manager_Basic.json`, current format. Lora Loader `widgets_values` =
    `[{"version":1,"textWidgetName":"text"}, "<lora:illustrious_all_rated_v1:0.60> <lora:69yottea_illu_v2:0.40> …", [4 rows]]`.
    The leading object is the original's hidden `__lm_autocomplete_meta_text` widget. Prompt nodes are
    `[{…}, text]`.
- **Catalogue entries** (r4a column only): at least two LoRA files in the test account's `loras` folder, for example
  tiny `bart_smoke_a.safetensors` and `bart_smoke_b.safetensors`. They only need to appear in the catalogue.
- **Sources:**
  - a STRING output for the Prompt sockets (any core string node);
  - a LORA_STACK output for the Combiner (a Lora Stacker's output works on both hosts).

## Steps

| # | Do | Expect (live) | Expect (with r4a/#11) |
|---|---|---|---|
| S1 | Cold-load with the rev 10 overlay; open the console | The 46 modules load, with 0 module-load failures (in particular none for `lm_frontends.js`'s relative imports). 0 `packerror`, 0 unhandled rejections, 0 lines starting `[LoRA Manager]`. **Record** any `DataCloneError` lines and their count: at most 3 per load can come from the refused widget-type calls, and they are not a failure | Same, and 0 `DataCloneError` |
| S2 | Add "Prompt (LoraManager)". Connect the STRING source to `trigger_words1`, then to `trigger_words2`. Then disconnect `trigger_words1` | Sockets `text`, `clip`, `trigger_words1`. After the connects, `trigger_words2` and then `trigger_words3` appear. After the disconnect, the empty socket goes and the rest renumber: `trigger_words1` (connected), `trigger_words2` (empty). 0 `packerror` | `text` is a text box with placeholder "Enter prompt... /character, /artist, /wildcard for quick search", not a socket. The sockets behave the same |
| S3 | Add "Lora Stack Combiner (LoraManager)". Connect the LORA_STACK source to `lora_stack2`, then to `lora_stack3`. Disconnect `lora_stack2` | Starts with `lora_stack1`, `lora_stack2`. Then `lora_stack3`, then `lora_stack4` appear. After the disconnect: `lora_stack1`, `lora_stack2` (connected), `lora_stack3` | Same |
| S4 | Add "Save Image (LoraManager)" and switch `file_format` png → webp → jpeg → png. Then route `POST /api/prompt` to record the body and answer `{"prompt_id":"smoke","number":0,"node_errors":{}}`. Set `filename_prefix` to `smoke_%date:yyyy-MM-dd%` and queue | `webp_method` shows only for webp, `jpeg_subsampling` only for jpeg. The posted `filename_prefix` is exactly `smoke_%date:yyyy-MM-dd%` (G1: no frontend expansion). 0 `packerror` | Same |
| S5 | Add "Debug Metadata (LoraManager)". Optional, if the lane can execute: run a small graph ending in it. Save and reload the workflow | A panel reading "No metadata available", with 0 `packerror`. After a run, the metadata shows as coloured JSON. After the reload, the panel reads "No metadata available" again (R6-4) | Same |
| S6 | Add Lora Loader, Lora Stacker and Create Hook LoRA | Loader and Stacker unchanged from main. Loader sockets: `model`, `text`, `loras`, `clip`, `lora_stack`. Stacker sockets: `text`, `loras`. Create Hook (new on live: main registers nothing for it): sockets `text`, `loras`, plus the native optional `prev_hooks`, which rev 10 adds. Each Create Hook logs one console warning, "LoRA Manager: text/loras widgets not found for Create Hook LoRA" (expected) | Each has a text box (placeholder "Search LoRAs to add...") and a rows editor ("LoRAs", search box, catalogue buttons, "Refresh catalogue"). Loader sockets: `model`, `clip`, `lora_stack`. Stacker: an optional `lora_stack` (added by rev 10). Create Hook: `prev_hooks`. No warning |
| S7 | Loader: click catalogue entry A, then B, then Remove on A | n/a | A row appears, outlined as selected. Within about 0.1 s the text reads `<lora:A:1.00>`, then `<lora:A:1.00> <lora:B:1.00>`, then `<lora:B:1.00>`. If the catalogue is refused (G6), the editor shows "[allowlist] … comfy.models.list …" and no catalogue buttons. Record that and use S8's typing instead |
| S8 | Loader: type `<lora:A:0.8> sunset,, glow` in the text box without pausing. Then set that row's strength to `0.5` and press Enter | n/a | A row A 0.80 appears. The text stays exactly as typed: not reformatted, no characters lost, caret in place. After the strength edit, the text reads `<lora:A:0.50> sunset, glow` |
| S9 | Export the workflow JSON, then reload it | n/a | The Loader's `widgets_values` are `[text, rows]`, with each row carrying name, strength, clipStrength, active, expanded, locked and selected. After the reload, the text and rows are unchanged |
| S10 | Create Hook LoRA: type `<lora:A:0.7>`, then toggle the row's Active off | n/a | A row A 0.70 appears. After the toggle, the row is dimmed and the text reads `<lora:A:0.70>` |
| S11 | Add WanVideo Lora Select, Text (LoraManager) and Lora Randomizer. Type `<lora:A:0.5>` into WanVideo's text | n/a | The widgets render: WanVideo text + rows, Text a text box, Randomizer rows. WanVideo's rows do **not** change: no sync is wired for it, which is expected |
| S11b | r4a only (r3). Save the workflow holding S10's Create Hook and S11's WanVideo and Text nodes (type a prompt into Text first), then reload it | n/a | Each comes back as saved. Create Hook: the text and its row (Active off). Text: the typed text. WanVideo: `low_mem_load` and `merge_loras` unchanged, plus the text and rows. Hook's rows are setter-normal (r4): `locked: false`, and no `clipStrength` of 0. The exported `widgets_values` are `[text, rows]` for Hook, `[text]` for Text and `[low_mem_load, merge_loras, text, rows]` for WanVideo. 0 `packerror` |
| S12 | Load `nunchaku-flux.1-dev.json`, then `Lora_Manager_Basic.json` | Loads with sockets, as main does today | Older format: the Loader shows its `<lora:Mezzotint_Artstyle_for_Flux_-_by_Ethanar:0.2> …` text and rows, and the Stacker shows `<lora:FLUX.1-Turbo-Alpha:1>` with 1 row. Current format, restored through the pack's migration: the Loader shows its `<lora:illustrious_all_rated_v1:0.60> …` text and 4 rows, the first selected (outlined), and both Prompts show their text. Then save and reload: nothing changes, and the saved Loader `widgets_values` are `[text, rows]`. **Fail** if the Loader's text box shows "LoRA text requires a string within the 262144-byte owned profile", which means the migration did not run. Nothing may crash |
| S13 | With `POST /api/prompt` routed as in S4, queue a graph containing a Loader with one row | n/a | **Record** the posted `text` and `loras` values exactly (arrays may arrive wrapped as `{"__value__": [...]}`) |
| S14 | Whole run | 0 `packerror`; 0 unhandled rejections; 0 lines starting `[LoRA Manager]`. The only LoRA Manager console output is S6's Create Hook warnings. TriggerWord Toggle is unchanged (held). Lora Info (rev 9) still mounts with "No LoRA selected" | Same, without the S6 warnings |

## Not covered

- **Original-format saves of Create Hook, Text and WanVideo (r3).** The pack has no current-format example of
  these nodes. Unit tests H1, X1 and V1 cover them with disclosed derived fixtures. The real WanVideo example is from
  before `merge_loras` existed, and core places it by position; that predates rev 10 and is recorded in
  `R3_CHANGES.md`, not repaired.

- **TriggerWord Toggle** stays off, under (c). A widget type that serializes its one value cannot reproduce the
  original's prompt form for tags with a strength: unit report T2 shows 5 of the 7 real-tag fixtures differ.
- **Held platform work:**
  - autocomplete, keyboard insertion and blur auto-format (G3, G4, G5);
  - node markers, manager settings, the workflow registry and templates.
- **Waiting on G1 and R6-4:** Save Image filename expansion (G1) and Debug Metadata restore (R6-4).
- **Other nodes' own frontends:** Lora Randomizer's randomization (RANDOMIZER_CONFIG) and WanVideo Lora Select's
  frontend extras.
- **G7:** the live sanitizer strips `aria-pressed`, `aria-checked` and `aria-expanded`, so rev 10 shows row state with
  inline styles instead. The selected row is bold and outlined; inactive rows are dimmed.

## Report back

- For each step: the result.
- S1: the module count and the console counts (`packerror`, `DataCloneError`, `[LoRA Manager]`, unhandled rejections).
- S7–S9: a screenshot of the Loader and the exported Loader JSON.
- S12: screenshots of `Lora_Manager_Basic.json`'s Loader and one Prompt, and the re-saved Loader JSON.
- S13: the posted Loader inputs.
