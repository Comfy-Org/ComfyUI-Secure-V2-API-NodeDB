# Lora Info (LoraManager): browser smoke plan for BART's lane

This checks what Tier R's fake API cannot: the live host stack (guest c6b97a15, host-entry 63d9437e, ui-renderer
bcf7ad64) running the port's `secure_web/lora_info.js`. MERVYN routes and selects it. Run it only after the Lora Info
revision is published.

## What changes the expected results

- **Request #15 (route assets runtime).** Without it, every Lora Info route is refused on its first asset call. Each
  step below lists the result for both cases.
- **The Loader's LORAS widget.** It is not registered on live (request #11 and the Loader frontend port), so nothing
  can push a selection to Lora Info yet. That is out of scope here.

## Fixtures

- `test/browser_fixtures/original_lora_info_workflow.json`: one Lora Info node saved by the original. Its
  `widgets_values[0]` is `{name: "ned_smoke_lora", notes: "Saved in the original", filePath: <absolute host path>,
  activeTab: "notes"}`.
- Optional, only if #15 is live: a tiny file `ned_smoke_lora.safetensors` in the test account's `loras` folder, with a
  `ned_smoke_lora.metadata.json` sidecar like Tier R's `a` fixture (notes plus Civitai `description` and
  `model.description` containing HTML).

## Steps

| # | Do | Expect (without #15) | Expect (with #15) |
|---|---|---|---|
| B1 | Add "Lora Info (LoraManager)" from the node library | An input `lora_source` with the optional (hollow) socket shape; a panel reading "No LoRA selected"; no `packerror` in the console | same |
| B2 | Connect any other node's output to `lora_source`, then disconnect it | The panel stays "No LoRA selected" (no selection source on live) | same |
| B3 | Load `original_lora_info_workflow.json` | **Record which happens:** (a) the panel shows "ned_smoke_lora" and "Saved in the original" (the host passes the saved `widgets_values` to `onConfigured`), or (b) it shows "No LoRA selected". Either is acceptable; the answer fixes the recorded old-workflow behaviour | same |
| B4 | If B3 was (a): click in Notes and type at least 20 characters without pausing | The caret stays put and no characters are lost (the panel must not re-render while you type) | same |
| B5 | If B3 was (a): click Save | An error toast (the route is refused) | With the optional fixtures present: toast "Saved / Notes updated successfully"; without them: an error toast "Lora not found: …" |
| B6 | If B3 was (a): switch to the Description tab | "Failed to load description" | With the fixtures: plain text "About this version" and "Model Description", with no bold, links or other HTML rendering |
| B7 | Save the workflow (export JSON), then reload it | The Lora Info node carries `lora_info: {name, notes, file, activeTab}` and **no absolute host path**; after reload the panel shows the same name and notes | same; `file` is the logical name once a lookup has run |
| B8 | Whole run | No `packerror` for onCreated, onConfigured, onSerialize or onConnectionsChanged; no error mentioning `getProperties` | same |

## Not covered

- The selection push from Lora Loader, Lora Stacker, Lora Randomizer or WanVideo Lora Select. It needs their LORAS
  widget on live (request #11 and the Loader frontend port).
- Real sidecar notes and descriptions on live. They need request #15.
- The original's HTML description rendering. Descriptions are plain text, a deliberate security difference.

## Report back

For each step: the result and a screenshot of the panel. For B3: which branch, (a) or (b). For B7: the exported JSON of the
Lora Info node.
