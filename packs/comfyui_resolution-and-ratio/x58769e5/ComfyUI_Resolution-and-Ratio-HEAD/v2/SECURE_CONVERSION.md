<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui_resolution-and-ratio

## Provenance

- Upstream: https://github.com/SamLiu1000/ComfyUI_Resolution-and-Ratio
- Exact pinned commit: `58769e57f190ff7d7a22ad0227f4caa0dfb3ac3c`.
- Release `x58769e5`; complete pristine capture `ComfyUI_Resolution-and-Ratio-HEAD` from `git archive` of verified fetched commit.
- Isolated base: central corpus `6fcbaa2cc92a39af8f631c8aecced0825f870997`, catalog 193 packs, SHA-256 `cee2cbc4d5af77549dac4b9d180720e9f3595025428ae24ad77af79d1012f6f9`.
- Selection: historical August 4 local registry download ranking, rank 1769 / 1968 downloads. This is not evidence of current trending. Pinned commit date September 8, 2026.
- Apache-2.0 license text, README and project metadata retained; V2 metadata adds explicit Python `>=3.13,<3.14`. No weights or external pack resources.

## Backend node dispositions

Actual pristine entrypoint imports without mocks: exactly 1 Python ID, `ResolutionAndRatio` (display `Resolution and Ratio`), category `CustomUtils`, two ordered INT outputs `width`, `height`. V2 preserves all nine input names, ordering, defaults, numeric bounds/steps, boolean labels, multiline default presets, combo `Custom`, category and output names/types.

| Exact backend ID | Implementation/evidence disposition | Registered in V2 | Review recommendation |
| --- | --- | --- | --- |
| `ResolutionAndRatio` | supported | yes | Bounded backend/frontend behavior; coordinator integration gates recorded separately. |

No backend nodes rejected or removed. Backend and frontend behavior gates pass under the generalized renderer fix described below. Coordinator review and serial integration remain required; this report does not itself increment the daily completed count.

The scalar algorithm stays in the pack. Reset precedes swap; Python banker's rounding, 8–32 free sizes, 32-grid rounding/clamping and direct ordinary out-of-schema scalar clamping match pristine. Ratio, scale and presets are frontend computation; the Python method intentionally does not recompute them.

## Frontend and ancillary scope

- Pristine: exactly one module / one extension `Comfy.ResolutionAndRatio`, zero JS-only graph nodes, zero routes.
- V2: one public definition extension for `ResolutionAndRatio`; no backend routes.
- Scoped mounted width/height editors write the original schema widgets through `setValue`. Other controls retain native widgets. There is no graph/prototype monkey-patching, backend fetch, browser persistence, ambient DOM, global keyboard interception, CDN or installation.
- Native `activate` fires on every user callback, including moves; it is NOT used as a dimension release event. Mounted pointer events distinguish live movement, release and cancellation.
- Pack-side code removes listeners, cancels reset/swap/deferred-preset timers, clears drag state and mounted children on removal/reconstruction. Instance keys include graph/node identity. The production bridge exercises these paths, including removal while a reset timer is pending. Remount retains the stable host widget/UI key and replaces its guest tree rather than detaching the host renderer container.

## Verification results

Observed preflight command (2026-10-06), from the isolated pack-db worktree:

```
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q -p no:cacheprovider packs/comfyui_resolution-and-ratio/x58769e5/ComfyUI_Resolution-and-Ratio-HEAD/v2/tests/test_resolution_ratio_secure_conversion.py -k 'not frontend and not artifact'
```

Observed **51 passed, 2 deselected** in 9.44s. Includes 32 fixed differential reset/swap/tie cases, 1000 deterministic randomized comparisons, malformed/bounded text/scalars, exact pristine/V2 schema/census, manifest/resource/stub/cache checks, actual separate-process zero-capability guest with raw-substitution denial, and real ComfyUI outer executor producing two Python INT values. CPU scalar computation has no untested GPU/model/credential path. The host ref runtime in the guest test is in-process; it is not a full user workflow.

Log: `/Users/ben/popbot/raw-chats/outputs/ned-oct6-resolution-ratio-backend-preflight.log`.

Production browser reproduction:

```
node packs/comfyui_resolution-and-ratio/x58769e5/ComfyUI_Resolution-and-Ratio-HEAD/v2/tests/resolution_ratio_bridge_harness.mjs
```

Uses actual SecureExtensionHost, guest worker, `allow-scripts` opaque-origin iframe, RPC and sanitizing closed-shadow Remote-DOM. Host node/widget collection is an explicit contract double; no claim of full LiteGraph native-renderer coverage. Native presets/dedup/floor, noncompounding scale and reset succeed. Real prolonged mouse drag reaches live 525 then 533, but the host renderer detaches/replaces the captured button. Outside movement/release never arrives; observed 533 vs expected snapped 864. No page/pack errors. **This gate fails and is retained.**

Log: `/Users/ben/popbot/raw-chats/outputs/ned-oct6-resolution-ratio-bridge-preflight.log`, SHA-256 `0904d7d4cf422e1082aec44cec9f1f0846bb4bd861502d15c1923f4d53cddb32`.

After the coordinator's generalized renderer fix, the expanded production bridge passes. It executes the pinned original JavaScript in a separate VM as a differential oracle for native callback behavior, presets/syntax/dedup/floor, ratio changes, scale/noncompounding base, swap/reset and edited dimension snapping. A real mouse drag held over 250ms settling intervals preserves element identity/capture and snaps to 864 on release outside. An explicit synthetic PointerEvent tests cancellation through the actual host/guest event channel; it is not substituted for the real mouse release test. Focus, malformed/oversized/adversarial text, serializable schema state, new-page/new-worker reconstruction, independently keyed nodes/graphs, remount subscriptions and pending-removal timer cleanup are exercised. The host-double's removed container may remain in the host UI cache, but it is detached, has no controls/event listeners and receives no further pack writes; no whole-host cache lifecycle claim is made.

Two expanded full-gate runs observed **53 passed** each (15.67s / 16.66s), including production bridge and exact byte reconstruction. Those ran while the coordinator was refining the generic renderer; they are preliminary rather than immutable dependency-pinned final evidence. Final command uses the same explicit core/bytecode settings above, omitting `-k`, and runs all 53 tests against the frozen dependency below. Final durable outputs are `outputs/ned-oct6-resolution-ratio-frozen-gate-1.log` and `outputs/ned-oct6-resolution-ratio-frozen-gate-2.log`; observed dependency hashes and final results are supplied in `outputs/ned-oct6-resolution-ratio-handoff.json`. No test-source-only claim or historical failing gate is promoted into a pass.

## Release integrity

- Canonical stub origin: KJ V2 composite in central corpus `packs/comfyui-kjnodes/x3f20054/ComfyUI-KJNodes-HEAD/v2`.
- d.ts SHA-256 `4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3`.
- pyi SHA-256 `50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78`.
- No shared stub/generator changes. Explicit canonical `COMFY_CORE_ROOT` and bytecode-disabled test imports. Pristine remains byte-identical to pinned source; no cache artifacts.
- Patch reconstruction is an integrity check, not a behavior certificate. The pair includes this report and the pack-local tests; regenerate after any byte changes, then run the final-byte gate twice.

## Authority and assets

- Backend `SDK_REFS=False`, no SDK permissions, frontend no additional permissions. No raw-compute authority.
- No filesystem/network/process/model/secret capability, weights or installs. Scalars cannot allocate tensors.
- Direct numeric values must be finite nonboolean scalars within absolute 1e9; flags must be booleans. Outputs are bounded 8–4096 before any downstream allocation. Preset label at most 128 characters; custom presets at most 64 KiB UTF-8 and 1024 lines. Malformed/oversized direct input fails closed; oversized frontend text is retained in its workflow widget but not parsed into choices, with a bounded error message. Queue execution rejects it rather than silently truncating authored text.
- Individual preset tokens reject non-safe integer overflow; normal preset dimensions above 4096 still parse but clamp when applied, like pristine. No new host allocation authority.

## Persistence and limitations

Authored `custom_presets`, selected preset, dimensions/ratio/scale/flags are **workflow-serialized schema widget state**, not reusable per-user library data. Ephemeral base dimensions/listeners/timers are reconstructed after configuration and do not persist in pack files or browser storage. Cloud per-render reset therefore needs workflow restoration, not a new KV service. The observed production bridge saves only schema widgets, recreates the entire page/opaque guest, restores authored choices/dimensions/scale, and uses restored presets successfully. Mounted controls are not included in prompt/workflow values. This is workflow-state continuity, not a proof of durable per-user KV or full end-to-end LiteGraph workflow save/load.

Pinned upstream quirks retained: backend banker's ties differ from JS `Math.round`; restoration sets the scale base from the restored displayed dimensions even if its scale widget is not 100; flags remain true for 200ms, so queuing during the transient flag window has upstream reset/swap semantics. Resource/type bounds intentionally narrow malformed/unbounded inputs; these are not security rejections of useful node intent.

## Resolved generalized runtime dependency

`frontend/src/ui-renderer.mjs` update clears listeners and executes `root.replaceChildren(next)` for every UI flush. `host-entry.mjs` dispatch calls `ui.update` unconditionally. Non-media keyed controls lose identity, pointer capture and potentially focus. Reproduction proves the captured element is disconnected, different from its replacement and no longer captured.

Coordinator implemented the smallest shared fix: reconcile already-sanitized keyed/tag-matched elements and safe attributes/children, retaining captured/focused controls and gesture lifetime. Sanitization, closed shadow and untrusted worker boundaries remain unchanged; no pack-specific host workaround was added. Original reproduction and failing log remain intact.

Frozen runtime base `f57f065d8500506cb8e148348079db722684306c` with coordinator-owned working renderer change: `frontend/src/ui-renderer.mjs` SHA-256 `01e7cef34f89b42257b74b9cc73d7235454dfa20535b2b450d2c2d7f679b9f5d`; exact `git diff -- frontend/src/ui-renderer.mjs` SHA-256 `bbf0bed4669ab7645844548866211b37fea85b4505b68b9955228a518147f190`. Coordinator generic evidence: `outputs/many-oct6-ui-renderer-final-evidence.json` and `outputs/many-oct6-ui-renderer-final.patch`; these are coordinator-observed runs, not NED-observed totals. Host entry SHA-256 `960dc6a6e7226f782b467d449dbec78f3e08447278be08bb12d30e1ebb96d052`, guest SHA-256 `b4b4e7bd932fd5eabce047cc5da06a7f1e3d3319079545d0bcac76315cc718e1`. The generic final change also preserves empty-to-nonempty textarea updates. Serial integration must retain the tested renderer revision (or rerun these gates against a later revision). NED has made no shared runtime edits.
