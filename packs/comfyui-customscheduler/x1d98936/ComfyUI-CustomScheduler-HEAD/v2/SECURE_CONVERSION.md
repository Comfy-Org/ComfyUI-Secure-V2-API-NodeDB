<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-customscheduler

## Provenance

Upstream https://github.com/BlakeOne/ComfyUI-CustomScheduler at exact Git commit `1d98936d111d01d6c4dfc078ab964cd615b2da97`, release `x1d98936`. The complete five-file retained snapshot matches every immutable upstream Git blob/path. `source-provenance.json` records original SHA-256, remote tree, actual root registration and negative central duplicate screen. Live HEAD was not substituted. Candidate comes from the retained corpus with unavailable/zero download field; no current trending claim. Original GPL-3.0 license and resources are retained byte-exact.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `CustomScheduler` | supported | yes | bounded declared scheduler contract; coordinator review required | All25 step counts, three seeded numeric controls each, native missing-key errors, source defaults, actual zero-capability guest and production outer float32 SIGMAS. |

Census: one Python node; no rejected or pending implementation. This is not user verification or central count promotion.

## Frontend and ancillary scope

| Frontend extension | Disposition | Scope |
| --- | --- | --- |
| `comfy.CustomScheduler` (`js/extension.js`) | supported | Show exactly steps+1 original sigma widgets, retain values/serialization, host-owned automatic height, change/configured/removal lifecycle and instance isolation. |

One frontend entry/extension; zero JS-only graph nodes and routes. Typed `defs.extend`, `setHidden`, `on('change')`, configured/removal hooks and `setSizeConstraints` replace value-descriptor/global-property monkey patches. No ambient DOM, global keyboard listener, network, browser storage or legacy bridge is used. Selection is by registered type, not mutable display title; renamed nodes keep their intended controls. Host auto-height replaces LiteGraph computeSize internals rather than promising identical renderer pixels.

## Behavior, bounds and authority

Input order, category, defaults, all26 optional FLOAT widgets including min/max/step/round, and one SIGMAS output are exact. The pack selects `sigma_0` through `sigma_steps` in original order; `SigmasRef.from_values` materializes exact CPU float32. No model/asset/raw/file/process capabilities are requested. This is the previously published public primitive, not a new shared API or private constructor.

Schema-admitted steps1..25 produce2..26 scalar values, at most104 final tensor bytes. Missing active optional sigma still raises the pinned `KeyError`; unused extra sigma values are ignored. Direct steps outside1..25/noninteger/boolean and sigma boolean/nested/negative/nonfinite values fail closed under the bounded public contract. These malformed direct-input admissions differ from Torch's accidental permissive conversions and are documented, not claimed unrestricted source parity. Source defaults are usable when all original widgets supply their values.

## Verification results

`tests/test_ned_customscheduler_conversion.py` covers genuine source/V2 census, complete schema/proxy/web declaration,75 float32 differentials across all step counts,25 missing-key controls, defaults/order/unused values, malformed bounds, two independently recreated required sandbox guests with zero capabilities and production outer SIGMAS, original source/GPL/stub/cache identity, and pristine patch plus ZIP byte reconstructions.

`tests/ned_customscheduler_browser.mjs` first measures pinned legacy visibility/value controls, then loads the actual converted extension through production SecureExtensionHost, sandbox iframe and worker. Tests exercise two independent nodes,1/25/7/4-step transitions, hidden edited sigma retention, configured rebind, serialized scalar reconstruction into fresh host widgets, old-listener reclamation, removal isolation, host destruction and exact `allow-scripts` (without same-origin). Host widget/graph fixtures implement the published operations; this proves actual secure transport/lifecycle, not full ComfyUI rendering or cloud deployment.

From `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_customscheduler_conversion.py -q
node ned_customscheduler_browser.mjs
```

Focused observed checkpoint:118 passed/1 artifact test deselected, browser production bridge passed. Final unchanged-byte repeated full runs are separately recorded with exact logs/hashes in the external handoff. Initial missing-web-manifest, path-vs-string assertion and browser host-fixture selector failures are retained, not reclassified as successful runs.

## Release integrity and dependencies

Python declaration `>=3.13,<3.14`, resolved3.13; installed Torch tested without runtime installation or weights. This does not attest sealed deployment provisioning. Python composite SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked frontend composite SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Both exact tested artifacts are retained, shared originals untouched. Separate Git correspondence and exact patch roundtrip prove provenance and reconstruction respectively.

## Persistence and limitations

State is only original workflow-owned scalar widgets. Hidden values are not omitted or replaced with defaults; reconstruction/configured hooks restore visibility from serialized steps. No durable authored files, process globals, cache, localStorage or per-user store exist. Fresh guest pack filesystems produce exact output with no continuity service needed.

Evidence is actual CPU tensors, macOS required sandbox guests, the real outer executor, and real opaque Chromium worker/iframe transport with host graph fixtures. No trained-model/GPU/Linux/cloud/authenticated multitenant or complete application-renderer/workflow claim. Malformed-input narrowing is explicit. Release integration and user verification remain coordinator-owned; no pending safe API intent was rejected.
