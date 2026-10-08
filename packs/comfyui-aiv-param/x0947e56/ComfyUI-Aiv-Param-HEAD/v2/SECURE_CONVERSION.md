<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-aiv-param

## Provenance

Upstream https://github.com/bbtaivi/ComfyUI-Aiv-Param at exact Git commit `0947e56320967d1e2b442297987547b7acaea64f`, release `x0947e56`. All six pristine paths, Git blobs and modes are verified in `source-provenance.json`; complete resources, Apache-2.0 LICENSE and authored instructions are retained. Retained queue ordinal92 has zero/unavailable downloads: no current trending or popularity claim.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `AivParam` | supported | yes | bounded workflow metadata, no execution effects | Exact two STRING schemas/defaults/tooltips, declared zero outputs, source defects retained, two fresh confined guests and production outer executor. |

One supported backend proposal, zero rejected/pending implementations within the explicit local scope. This is not coordinator integration/count promotion or cloud deployment certification.

The source execution method accepts no declared arguments: calling it with text_param/text_note raises TypeError, while its no-argument body returns None. MANY explicitly approved the narrow callability repair: accept the two existing STRING arguments and return explicit zero-output io.NodeOutput(), with no parsing, new sockets, state service or effect. Canonical NodeOutput.args is empty and result is None. Native controls remain separate from repaired success. IDs, display name, category, dynamicPrompts, required/default/multiline/tooltip settings and zero-output/non-output-node contract are unchanged.

## Frontend and ancillary scope

| Pristine extension | Disposition | V2 mechanism | Evidence |
| --- | --- | --- | --- |
| `AivApp` | supported | scoped defs.extend/onCreated/onConfigured/onRemoved, native widget setValue and public beforeSerialize | Pinned setter/getter controls plus actual opaque iframe/worker and canonical asynchronous serialization leaf. |

One extension, zero JS-only graph nodes and routes. No ambient DOM, parent-window, global keyboard, storage, fetch or legacy bridge. The original text_param getter escapes every brace for saved workflow/API metadata; its setter removes one preceding backslash before braces for display. Native editing is intentionally left in the original widget. V2 applies the exact escaping at workflow, prompt and embedded serialization destinations without mutating the edited value; configured/reconstructed values are cleaned through the public widget facade. text_note is untouched. Invalid JSON and adversarial HTML are literal text, not parsed/rendered.

The browser harness exercises eleven source vectors including Unicode, line breaks, malformed JSON, literal markup, double backslashes and maximum all-brace text; repeated save, three destinations, no compounding/widget mutation, reload into fresh node instances, two-node isolation, repeated configure, oversize/corrupt refusal and recovery, removal during pending save, subscription cleanup and host destruction. Required subscriptions are two widget projections plus one workflow lifecycle observer.

This proves the production SecureExtensionHost/opaque worker routing and tested canonical serialization leaf with widget/graph fixtures. It does not certify every full-application API-export caller, bare synchronous graph.serialize, browser deployment or arbitrary cross-pack programmatic setter/getter interception. The V2 public getValue remains native editable text rather than the source's ambient property override; intended owned edit/configure/save flows are tested.

## Workload, authority and persistence

Zero backend and frontend permissions. No dependencies beyond public SDK/browser facade, no downloads, runtime installation, models, files, network or secrets. Raw editable text_param is bounded to64KiB UTF-8 before serialization; maximum projection/restored input128KiB. Backend text_param128KiB/text_note64KiB, strict STRING, no JSON interpretation. These are explicit supported workloads, not source maxima. Oversize/corrupt values are refused without resets.

Persistence disposition: authored node-owned metadata stays in workflow-serialized original widgets. A fresh workflow generation/node reconstruction restores edited text and notes; two fresh backend pack filesystems/PIDs accept the saved strings without state effects. No independent reusable user documents/KV/process-global persistence exists or is claimed. No cloud backing claim is needed for node-owned saved graph state.

## Verification and runtime

Run from v2/tests:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_aivparam_conversion.py -q
```

Tests cover exact actual census/schema, approved zero-effect execution/native defects, bounds, two recreated required Seatbelt guests/production executor, actual Chromium opaque iframe/worker, manifest/resources/Apache provenance/current stub hashes/cache hygiene, patch+ZIP two byte-exact reconstructions and wrong-pristine refusal. Separate frozen handoff records actual whole-suite results and source fingerprints, not historical pass assertions.

Python3.13 core explicitly selected; composite pyi origin many-oct7-font-catalogue-comfy-api.pyi SHA `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`; checked d.ts SHA `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Existing public serialization contract consumes root's tested implementation repair indexed by outputs/many-oct7-widget-serialization-evidence.json; no shared edits or declaration changes here.

Initial fixture failures (function selector refusal, missed workflow observer, zero-output result representation) and omitted frontend manifest web_directory are preserved in unique diagnostic logs. Corrections do not relax byte/text/schema assertions or enlarge timeout/authority. Linux/cloud provisioning, complete user-workflow/API export and hard physical resource enforcement remain separate unproved deployment boundaries.
