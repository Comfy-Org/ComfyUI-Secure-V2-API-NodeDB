# Secure Nodes V2 conversion evidence

This is a source revision of the existing four-node SimpleSwitch conversion.
Upstream: https://github.com/boobkake22/ComfyUI-SimpleSwitch
Commit: 5a4f403a2f4aac076cee89ffe8ff4e93511c9acc (x5a4f403).
Tree: d8e50f29423d592f2390231e902a0eb2a4315819.
All seven original files and their 100644 Git modes match independently fetched
upstream objects. The four registered IDs are SimpleSwitch, SimpleLatentSwitch,
SimpleAudioLatentSwitch and SimpleVideoLatentSwitch; there are no frontend
extensions or routes. The six optional sockets remain ordered input01..input06,
with the original wildcard/latent types, output name and Simple Switch category.

The reviewed nodes.py repair restores dictionary-subclass handling through
isinstance(value, dict). All-None model/clip context subclasses are skipped by
the generic switch; latent subclasses remain eligible for first-match selection.
Nested audio remains accepted before shape access. Rejected nested video reads
shape while constructing the original diagnostic, preserving the native
RuntimeError and its full message, including before a later valid input. No
exception text is synthesized. Returned native objects and genuine reference
wrappers retain identity; no clone, coercion, schema or permission change occurs.
SDK_REFS remains true for all four nodes. Generic/audio/video retain the raw
permission; the plain latent switch has no permissions.

The first selected actual attempt remains FAILED with five native differences:
three dictionary-subclass selections and two nested-video diagnostic outcomes.
Its worker result and exact errors remain in the retained failed R1 evidence.
The separately authorized corrective R2 ran the same 95 native cases and 24
genuine default-provider reference cases, with unchanged scientific harness,
fixtures and controls. All 119 matched, including all five former differences.
All tensor/dictionary/metadata identity and content fingerprints were unchanged.
Four schemas, normal manifest generation, canonical pair and bundle, two
pristine byte/mode replays, wrong-selection and changed-base controls passed.
No automatic retry occurred.

Actual archive SHA256:
17fd558c5f6de0c681205210537c540d5f4433016cde4e9853b712856dca397f
Independent strict intake SHA256:
7ee25bc724ade5021eaf509a1558af35cea67dcff9bbcbecd986b9315695d9a3
The run took 2.4883 monotonic seconds. Observed aggregate RSS peaked at
358,924,288 bytes under a 1 GiB watchdog; this is not a hard memory quota.
All input, runtime, full-site (84,917 files), component (96 files) and
configuration before/after maps matched. Both owned process groups were
independently absent twice after cleanup. There were no fixture/lifecycle errors.

The actual four-node secure-nodes.json is retained byte-exact. Only this evidence
document changes after the native run. Final canonical file-only pair/bundle
generation and two fresh pristine replays verify the final source bytes and
explicit 100644 modes. No SDK, node or normal manifest-generator rerun occurs.
Derived ZIPs and large raw logs are excluded from the publication inventory.

Qualification covers the tested native/default-provider components. It does not
establish Guest transport, raw-capability enforcement, shared TEST, service,
managed deployment or whole installed readiness. Root owns final PR32 review,
publication and registry handoff. Historical tests retained in v2 are source
reference material, not an additional current acceptance claim.
