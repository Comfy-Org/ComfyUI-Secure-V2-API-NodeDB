# Secure Nodes V2 conversion

## Identity and census

Pinned upstream https://github.com/ShmuelRonen/ComfyUI-HunyuanVideoStyler at `37a6b602f648a14a4fecf796f7af21a755de51f1`. All 18 pristine files match exact Git blobs and file modes; `source-provenance.json` records full correspondence. Retained queue position 179, downloads unavailable/zero, not a current trending/popularity claim.

Actual entrypoint census: one Python ID; zero frontend extensions, JS-only nodes and routes.

| Node ID | Disposition | Evidence and scope |
| --- | --- | --- |
| HunyuanVideoStyler | supported | Exact source prompt algorithm, all 206 immutable templates, ten-category ordered composition, zero-capability confined guests and production outer two-STRING contract. |

## Backend behavior

The complete `HunyuanVideoStyler.py` is retained byte-exact. A V3 wrapper preserves the original ID, display name, category, ordered schema/options/defaults, debug label and named output order. Explicit value mode has zero permissions; immutable pack-owned resource reads do not expose arbitrary input paths or a host file catalogue.

Preserved: first-choice None then sorted menu names; all ten style categories; source fixed category application order; literal `{prompt}` replacement; comma joining only truthy negative text; skipped None/empty/falsy selections; invalid selected name KeyError; ignored unknown extra kwargs; exact debug-stage printed text. Adversarial HTML/path strings remain literal text, not DOM or file operations.

Eleven bundled JSON files yield 206 non-None templates, with no duplicate group/name collisions. Filesystem enumeration order consequently does not affect selected template semantics; no sorting or relocated data repairs are introduced. The extra time-of-day file located under weather remains in weather exactly as pinned.

Admission bounds total prompt input and each projected combined output to 65,536 UTF-8 bytes, cumulative composition work to 512 KiB, and requires STRING prompts/Boolean debug. Projection uses fixed template byte lengths and placeholder multiplicities before calling the source. Native useful invalid-selection controls are retained; over-bound or wrong schema-type inputs fail closed.

## Frontend and persistence

Frontend axis not applicable: no JS or mounted UI. Ordinary host widgets own serialized workflow selections/prompts.

No mutable authored preset mechanism, file-writing route, process cache or external service exists in the pinned source. README extension intent is contribution via pull request, not editable runtime state. Bundled JSON is immutable pack resource state; workflow inputs carry user selections and text. Two recreated guest roots/PIDs with different host tenant identities use the same pinned data and reproduce exact outputs. No durable/cloud KV claim is made.

## Dependencies and resources

Standard-library JSON/pathlib only for runtime composition, admitted Python 3.13. No model, tensor raw, network, subprocess, runtime installation or weight requirement. All source/data/workflow/MIT license resources are preserved byte-for-byte except the V2 import entrypoint. Added runtime metadata declares Python >=3.13,<3.14; no installer operation.

Public composite declarations pinned byte-exact to coordinator artifacts:
- Python `many-oct7-font-catalogue-comfy-api.pyi`, SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`.
- Frontend `many-oct6-model-catalogue-checked-comfy-api.d.ts`, SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`.

## Evidence

Unique suite `v2/tests/test_amy_styler_conversion.py`: exact schema/proxy and source bytes; every template against six blank/comma/braces/Unicode/adversarial-text controls; all-category chaining and debug/invalid cases; bounded input/projected-work refusal; two fresh required Seatbelt zero-capability guests, actual outer two-STRING output, corruption-free recovery; complete resources/stubs/manifest/cache hygiene; stored pair and ZIP pristine→V2 reconstruction twice with wrong-source refusal.

Run from tests with explicit `COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes`, `PYTHONDONTWRITEBYTECODE=1`, Python `-B`, pytest `-c pytest.ini -p no:cacheprovider`. Observed final results and source fingerprints are external frozen AMY handoff/log evidence, not inferred from registration.

Local pure text behavior is supported within admitted workload. This does not certify Linux/cloud deployment, client rendering, translated model quality or end-user generation workflows. No model double or trained model inference is needed for the text-only algorithm. Coordinator alone reviews/integrates/catalogues the complete pack.
