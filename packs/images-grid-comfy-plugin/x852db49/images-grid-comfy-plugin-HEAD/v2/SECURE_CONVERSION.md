# ImagesGrid Secure Nodes V2 source revision and qualification

Pinned upstream: https://github.com/LEv145/images-grid-comfy-plugin at
852db490ef93702e1c68fe9774bdf65aaa7d3574, tree
d46251eeab3c43e670ebe90d62fb3a6c7e2709ae. All 29 original files and
100644 Git modes are retained. Five registered node IDs: LatentCombine,
ImagesGridByColumns, ImagesGridByRows, ImageCombine and GridAnnotation.
There are no frontend registrations, routes, model loads or forwards.

The source revision replaces two private ImageRef._from_raw return sites with
public ImageRef.from_tensor, covering ImageCombine and both shared grid classes.
All other tested executable bytes, schemas and permissions are unchanged.
GridAnnotation uses a bounded text/font-size data descriptor; its consumers
reconstruct the unchanged vendored Roboto font. LatentCombine preserves the
original samples-only return, including dropping unrelated latent metadata.

The selected actual default in-process SDK run passed 76 exact native comparisons:
68 returns and eight intentional original errors. Six additional exact-message
ValueError profile refusals are separate from native parity. All five real schemas
validated. Genuine refs were created and released in 69 cases, with unchanged
input identity/content/metadata fingerprints and no fixture/lifecycle errors.
Annotation text/font-size semantics and the consumers' rendered pixels were
compared; live Pillow font identity is not claimed. Wrong-expected and changed-base
controls refused their respective changes. This is finite enumerated evidence.

The actual run generated secure-nodes.json once, with only five null loop_boundary
metadata additions from the retained manifest. Canonical pair/bundle generation
and two pristine byte/mode replays passed. The actual generated manifest is retained
byte-exact in this source handoff. All 84,917 site, 96 component, 141 SDK, 1,384 Core
and 83 backend file maps were unchanged. Actual Torch intraop/interop counts were 1.
Three task PIDs and two groups were independently absent twice after cleanup.
Public evidence contains task-only projections; full-host process records remain
in the private immutable terminal archive.

Actual owner elapsed 58.510221875 seconds; payload plus cleanup 3.90024 seconds.
Sampled payload/descendant peak RSS was 348,356,608 bytes, excluding the controller.
The separate external time -l maximum resident set was 1,057,128,448 bytes.
These are observations under a sampled watchdog, not hard resource quotas.
The frozen inner supervisor was reference-only; no supervisor PASS is synthesized.

Declared source limits include 4,096 input images, 16,384 pixels per output axis
and 512 MiB produced batch. The six refusal cases do not prove all resource bounds.
The managed transport and permission purposes remain explicit qualification gaps:
Guest IMAGE/LATENT/custom annotation transport, broker raw-capability enforcement,
managed dependency/installed profile, and shared-service/admission behavior.
The current public constructor is source- and default-provider-qualified; an old
SDK without that constructor is not qualified by this result. There is no live
Guest, service, registry admission or whole-pack readiness claim.

Only this evidence document changes after the selected native run. Final canonical
stdlib file-only packaging and pristine replays bind this document and the exact
tested code/manifest; they do not rerun any SDK, node or normal manifest generator.
Root owns source review, publication and any later admission decision.

Actual result archive SHA256:
a9d486253051532c3c8ed240433aa3a8a5360f44e14f35869bf5b556593fb162
