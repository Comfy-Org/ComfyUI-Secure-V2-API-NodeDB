# LayerStyle backend conversion

Status: 3 full and 3 partial adapters of 171 declared node types; the other 165 retain their real schemas and named validation/execution refusals. Frontend, models and GPU purposes remain unqualified.

Full adapters: `LayerColor: HSV`, `LayerColor: RGB`, `LayerUtility: ImageScaleByAspectRatio V2`.
Partial adapters: `LayerUtility: ImageBlendAdvance`, `LayerUtility: ImageBlend`, `LayerStyle: DropShadow`. `ADAPTER-DISPOSITIONS.json` lists every node.

The identity pin is 557d882e184c7b702208cc7805659b10dfa06c59. The repair base consists of 517 exact retained corpus pristine files at 31a82556e4b4118dd1f1b57e8bb23cd28aa21807, before canonical omissions. An independent upstream Git-tree verification is not claimed. V2 is a full mirror of the retained source, with qualified boundary files overlaid; unselected algorithms remain present and unimported.

The six original node modules are byte-identical. Eighteen reachable image helper functions and the blend-mode list are exact source spans. All original node IDs, input names, defaults/options, output names/types and schema metadata remain intact. The real selected encoder adds only its nullable `loop_boundary` extension; it remains in the manifest. The comparison removes this sole extension only when the retained field was absent and its actual value is null.

Known differences: eleven blend modes require unavailable OpenCV/scikit-image and refuse by node name only when the original reaches the dependent helper: color_burn, color_dodge, linear_burn, linear_dodge, overlay, soft_light, hard_light, vivid_light, pin_light, linear_light and hard_mix. The eight Pillow modes normal, multply, screen, add, subtract, difference, darker and lighter use the original algorithms; `multply` is the original option spelling. DropShadow nonzero mask growth requires unavailable SciPy and refuses only when reached. Earlier original errors, the zero-distance error and the missing-mask identity path are preserved. Validation probes original control flow without publishing output refs or logs.

The common-lock dependency slice is used; no optional numerical dependency profile is declared or inferred from installed gate extras. Minimum public SDK base: 0cd9adec. IMAGE and MASK retain their declared wire kinds, dtype/shape/stride/storage offset and logical bytes; identity outputs retain the original host ref. Original None results and BOX lists are preserved. API contracts are unchanged copies.

Synthetic direct and actual development GuestSession runs each passed the same 493 inputs: 272 exact outputs, 19 exact original errors and 202 explicit refusals. All 171 typed schemas, 7 constructor controls, output-kind/layout/input-mutation checks and negative controls passed. The actual child checked its selected SDK pins, denied undeclared SciPy before and after the cases, and passed a connected MASK consumer/None/wrong-VALUE test. These are CPU development-gate results; no browser, OS-confinement or live deployment claim is made. A final full-mirror rerun and artifact review are prerequisites for publication; their receipts accompany the private handoff.

No WEB_DIRECTORY, routes, network, model weights or frontend permissions are declared. Retained frontend source/assets are unqualified. Canonical media/workflow/model omissions apply to both siblings. An unused bundled font is omitted because its separate redistribution grant is unverified; no illegality claim is made.
