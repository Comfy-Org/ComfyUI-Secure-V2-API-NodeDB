<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — Image Analysis Tools

## Provenance

- Upstream: https://github.com/ThatGlennD/ComfyUI-Image-Analysis-Tools
- Exact historical commit: `167e3950de73d25c482648b19fb06b2b42a7775b`; release `x167e395/ComfyUI-Image-Analysis-Tools-HEAD`.
- Registry release 1.2.0: https://cdn.comfy.org/verevolf/ComfyUI-Image-Analysis-Tools/1.2.0/node.zip — 28,947 bytes, SHA-256 `67d9036c9c893e42bb67ac5380c200ef449eca62bca8a4e56f2dcb10fc0afd59`.
- All 20 release paths/blob bytes/executable modes match this Git commit; independently verified correspondence packet SHA-256 `e894a510459e1f3aa7d2f938633ee374298ca2bad79b5c7541e5f81d016fe894`. Complete pristine capture: 74,561 bytes; `nodes/defocus_analysis.py` is executable (Git 100755). The retained corpus lost that mode; it remains frozen and was not substituted for the verified release/Git mode.
- Live commit `5a26d6eb7c828c44b40e29a71bfc0104361e38a6` fixes registration naming but is NOT substituted. Selection is retained historical queue row25, not a current-trending/download-ranking claim.
- `pyproject.toml` declares MIT, but no LICENSE file is supplied. This is a provenance caveat, not a supplied-license assertion.
- All original file hashes and modes are in `tests/pristine-files.json`. Pristine files are unchanged; imports disable bytecode.

## Backend dispositions

Twelve literal `NODE_CLASS_MAPPINGS` IDs, not 24. Each original schema declares a different camel-case ID. V2 keeps the original registered graph IDs and display-name map; it normalizes only schema `node_id`/`display_name` to those registrations. Inputs, choices, defaults, outputs, categories and numerical methods remain source-exact. This naming normalization is explicit, not an invented alias or live-source fix.

All 12 are recommended supported within the selected bounded Mac development workload after positive source/actual-guest evidence. Central intake is coordinator-owned; no central count, sealed/Linux/Cloud or user-workflow certification is declared here.

| Exact registered backend ID | Original schema ID | Bounded behavior / focused evidence |
| --- | --- | --- |
| RGB Histogram Renderer | RGBHistogramRenderer | First-image uint8 RGB conversion, ordered 256-bin plots, native PNG controls. |
| Sharpness / Focus Score | SharpnessFocusScore | Laplacian/Tenengrad/hybrid, source normalization and visualizations. |
| Noise Estimation | NoiseEstimation | Gaussian residual, local/global block metrics, native fallback behavior. |
| Contrast Analysis | ContrastAnalysis | RMS/Michelson/local methods, native uint8 overflow and partial-block behavior. |
| Entropy Analysis | EntropyAnalysis | Local/global histograms/entropy and block visualization. |
| Blur Detection | BlurDetection | Laplacian variance, local/global metrics, normalization and heatmap. |
| Edge Density Analysis | EdgeDensityAnalysis | Canny/Sobel, source overlay/block density, constant-image native warnings. |
| Clipping Analysis | ClippingAnalysis | Shadow/highlight thresholds and source overlay/result order. |
| Color Cast Detector | ColorCastDetector | Channel imbalance/neutrality, native uint8 overflow and zero/nonfinite semantics. |
| Color Harmony Analyzer | ColorHarmonyAnalyzer | Native hue extraction, KMeans, all harmony rules and polar visualization; explicit local RNG normalization. |
| Color Temperature Estimator | ColorTemperatureEstimator | Native XYZ/McCamy metric, integer output and colored preview. |
| Defocus Analysis | DefocusAnalysis | Native FFT sum/mean/hybrid, Sobel/Canny edge-width, interpretation and two image outputs. |

All rows are positively exercised in `tests/test_image_analysis.py::test_all_options_png_outputs_and_rng_differential`, `::test_native_malformed_small_domains_and_first_batch`, and `::test_all12_required_guests_production_outer_and_cap_denials`; schema/source-body proofs are separate in `::test_pristine_census_schemas_ids_and_ast_preserved`. Registration/schema alone is not the behavior evidence.

## Frontend and ancillary scope

Exactly one startup extension, ID `comfyui.image_analysis_tools`, and no JS-only graph nodes, routes, widgets, models or UI application. Its sole legacy behavior is logging `ComfyUI Image Analysis Tools Loaded` on setup; V2 uses typed `comfy.onReady`. `tests/frontend_harness.mjs` proves callback/message and refuses ambient DOM/window/network/storage access. This is a startup-module VM harness, not browser/deployed worker certification.

Numerical/FFT/KMeans/plot algorithms stay in `algorithms/`; no bridge to the old ComfyNode classes or shared-core transplant. All method bodies are AST-compared after only class-to-function calls and the declared KMeans RNG parameter. Helpers preserve pixels and PNG controls while adding preallocation/publication checks.

## Authority and dependencies

All nodes declare `SDK_REFS=True` and exactly `inspect, raw`. Public `ImageRef.describe` provides shape before input buffer import; public `raw` reads pixels; inherited public `ImageRef.from_value` publishes IMAGE outputs. No private ref constructors/attributes, host object recovery, network, arbitrary paths, installation or process access is used.

Selected existing unsealed Mac CPython 3.13.14 runtime: NumPy 2.4.6, OpenCV 5.0.0.93, Matplotlib 3.11.1, scikit-learn 1.9.0, Pillow 12.3.0, Torch 2.13.0 and transitive SciPy 1.18.0. Upstream requirements are unversioned; these are explicit selected development versions, not historical packaging equivalence. `pyproject.toml`, `requirements.txt` and `DEVELOPMENT_RUNTIME.json` declare the selected dependencies. Existing OpenCV headless/non-headless distributions coexist; AV/CV duplicate ObjC and other native diagnostics remain visible, not suppressed or repaired. No installation occurred.

Development guest selection replaces ONLY resolved `spec.pack_root` with the owned V2/fresh copy. Existing interpreter/library roots, required Seatbelt kernel policy, IPC, tenant identity and capabilities remain unchanged. Runtime-probe classes are test-only and absent from the manifest. Existing public stub bytes are pinned: Python `57246795795118e320926fbbb6be50f7c03c6971b2b5029ac709adef5169ab03`; frontend `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. No unused new contract churn.

## Behavior and observed verification

- Source versus converted schema and every numerical method body are compared separately. Source class extraction `cls/self` and native NumPy float64 guard defects were caught by early RED runs and fixed pack-side; original logs remain in the owner evidence directory.
- **62** declared option/visualization combinations: exact scalar/text/dtype/shape and zero-tolerance PNG pixel comparisons under the selected scientific/font runtime. Native PNG controls remain PNG, 150 dpi, tight bounding box, white facecolor. `FigureCanvasAgg` is render-local; no pyplot manager, global backend/rc selection or global RNG mutation. Test oracle alone selects headless Agg and a JACK-owned font-cache directory; the guest runtime is not broadened by this.
- **83** admitted small-domain comparisons: black/white images, 1/2/4 channels, block 0/-1/8/128, clusters 0/-1/8. Two source uncaught exceptions remain failures; source caught failures remain their original fallbacks/messages. Native algorithms still select only the first image from a batch. No partial blocks, hue rules, overflow, nonfinite result or metric is silently corrected.
- KMeans keeps native `n_init='auto'` and its selected library's default maximum 300 iterations. Production uses a new per-execution `RandomState`, not global NumPy state. Fixed initial state 41 proves native draw sequence/results in-process. Ambient cross-execution RNG continuation is deliberately normalized; random clustering results are not guaranteed identical across executions. Actual guest default Harmony uses constant hue to avoid invented seed authority.
- Real required Seatbelt guests exercise all 12 through production outer map/resolve/unwrap with pixel-exact IMAGE outputs; separate native block-zero fallback, uncaught 2-channel defocus failure, dimension refusal, raw/inspect denial and recovery are covered. A separate required guest proves outside-root read/import refusal and recovery and records actual library versions/origins without pyplot loaded.
- Final full gates and exact final logs are recorded in the immutable JACK handoff packet after completion. Development REDs and harness-loading diagnostics are preserved as predecessor evidence, not reported as passing runs.
- Observed development full gate: **15/15 passed**, 24.55s (`full-development4.log`); required guest PIDs 91858/92194 exercised all12 through the production outer executor, and boundary PID92409 proved outside-root refusal/recovery. Final two runs use the final artifact bytes with additional after-render library-state confirmation, recorded separately in the handoff; this historical development pass is not retroactively relabeled as those runs.

## Persistence and bounded workload

No durable authored libraries, endpoint/file writes, workflow-mutated state, model cache or cross-render pack data. Input image/options are workflow-owned; output tensors/figures/PNG bytes/local RNG are render-local. Two fresh guest roots prove continuity of stateless input→output behavior, not durable cloud storage. Matplotlib may use its library font cache inside the host-provided guest scratch/HOME; no pack-local authored persistence is inferred.

Supported local envelope, NOT pristine-domain or kernel resource equivalence:

- BHWC: batch 1..4, height/width 1..1024, channels 1..4; reserve 16 bytes per input element before raw buffer import, total ≤64MiB.
- Conservative projected buffer/FFT/plot workspace: input reserve +96 bytes per first-image pixel +32MiB plot reserve ≤192MiB. Scientific-library resident memory, allocator/native peaks and hard physical CPU/RAM profiles are NOT proven by this estimate.
- Block magnitude ≤128; cluster magnitude ≤8; preserve zero/negative native errors/fallbacks inside this envelope. Projected KMeans work `pixels * max(1,abs(clusters)) *304` ≤300M before allocation; this is not a measured execution-time guarantee or an iteration change.
- Options are closed builtin scalars, strings ≤128 UTF-8 bytes, integer bit length ≤32. No clamp/coercion or metric change.
- Figure width/height ≤6 inches, DPI ≤150 before canvas construction; source labels/options remain bounded. A twofold tight-box margin projects ≤64MiB before PNG render. Encoded PNG writes ≤16MiB; decoded pixel reserve ≤64MiB checked before RGB/NumPy conversion. Aggregate published IMAGE tensors ≤64MiB; text ≤64KiB. Figures are cleared on normal/error paths; no global figure registry.

## Release integrity and remaining limitations

Manifest accounts for every exact ID and the one frontend entrypoint. Pristine→V2 pair and ZIP roundtrip validate complete final bytes/modes, including executable pristine defocus mode and resources. No bytecode/cache litter is permitted in pristine or V2. Test-only boundary/runtime probes are excluded from release registrations.

Sealed dependency lock/base/ABI, Linux wheels/runtime, Cloud activation, deployed frontend/worker behavior, hardware profiles and ordinary larger workloads remain unproven. A bounded Mac development recommendation is not a universal runtime/physical-memory guarantee, human verification or compatible workflow count. No shared files, catalog, old packets, commits or pushes are changed by this handoff.
