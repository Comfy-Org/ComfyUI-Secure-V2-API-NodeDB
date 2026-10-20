# Studio Nodes — Secure Nodes V2 (three original nodes)

This source conversion is pinned to
`comfyuistudio/ComfyUI-Studio-nodes@bda7ac852be94033e223b7ea1f79ac4245fb7475`,
the historical three-node tree `9f7b8c6b6c754bd0c5620848c31ce19f81e37147`.
All five tracked original files remain byte-exact. This is not the newer
seven-node revision. No upstream license or publisher identity is invented.

The selected source-backed native/default-SDK/required-Seatbelt Guest comparison
passed 292 ordinary cases. This qualifies the finite purposes below in the
tested development profile. It does not establish production dependency-profile
admission, public graph/browser behavior, registry adoption or deployed-service
acceptance.

| Original node ID | Tested purpose and finite scope |
| --- | --- |
| `AspectRatioImageSize` | 140 cases: seven widths (64, 65, 72, 127, 128, 512, 4096), all ten original aspect ratios and both directions; exact integer dimensions, Python rounding and resolution labels. |
| `AspectRatioResizeImage` | 144 cases: original Stretch/Crop branches, both directions and all ten ratios in the base suite; nonuniform wide/tall/square fixtures, odd crop centering, clipping/uint8 quantization, RGB/RGBA, and distinct two-image batches in the additional suite. Exact decoded float32 output shape/pixels and labels. |
| `MarkdownModelNote` | Eight cases: defaults, empty strings, Unicode, Markdown-sensitive text, newlines, path-like strings and surrounding whitespace; exact formatted text including trailing spaces. No download, path resolution or filesystem write is performed by this node. |

All three schemas match the original IDs, display names, categories, required
input order, defaults, ordered options, output types/names/order and the
`info` widget's `editable=False` metadata. Metadata comparison does not qualify
actual browser rendering or editing behavior. Width 65 is a direct component
case; UI step metadata and public graph validation were not independently tested.

## Boundary and unchanged computation

`studio_nodes.py` contains the real module-global classes the Guest imports.
The original three compute methods were textually extracted because the legacy
package imports the unused host `folder_paths` module. Their method text and AST
remain unchanged. The V2 package initializer only imports the mappings.

All three nodes declare `SDK_REFS=True`. Only the resize node requests `raw`:
it reads `image.raw()`, calls the unchanged original method, and returns the
result through the public `sdk.ImageRef.from_tensor` constructor. The scalar
dimension and Markdown nodes request no capabilities.

The resize node intentionally processes **only `image[0]`**, as upstream does.
It keeps NumPy clipping and uint8 truncation, PIL `Image.LANCZOS`, original
center-crop branch/truncation rules, target-dimension rounding and the final
float32/BHWC conversion. It is not generalized to preserve every batch image.
RGBA alpha handling is compared to the same original PIL path. The scientific
worker compared decoded tensors directly in memory using exact `torch.equal`,
shape/dtype checks and labels; retained records contain matching tensor hashes.
Encoded image-byte parity is not claimed.

The 144 resize cases cover a bounded set of image sizes and branch combinations,
not every image allocation at the schema's maximum width. Empty-batch,
one-channel and unknown-ratio diagnostic probes remain separately proposed and
unrun; they do not count among the 292 ordinary passing cases. An exception from
an ordinary case is a failure, even if another side raises the same exception.

## Actual selected execution

One attempt was selected by `m_e9cf28e327`. It used:

- Python 3.13.14, Core `44564d0279c275eef52b11750a9d76349f4e7a88` and backend
  `59bd3e1acba6520bb32717ad03833f6ab2967ecc`;
- genuine public SDK source
  `f1a73e4f160e70862f51abdddbb9268e2ce94dd96e18455a79e42307a443f91c`;
- actual Torch 2.13.0, NumPy 2.4.6 and Pillow 12.3.0;
- the trusted normal-site Host (`-I -B`) and one actual required-Seatbelt Guest,
  with real Host IMAGE ref creation, brokered raw access, output resolution and
  explicit ref release. No local converted-node execution fallback was used.

The attempt completed 292 native comparisons and 292 genuine Guest dispatches
in one Guest, three schema checks and five poisoned comparator controls
(label, pixel, arity, error and paired-matching-error rejection). Inputs remained
unchanged. No model weights, model forwards or downloads were used.

The observed whole-owner time was 38.9422468 seconds; observed payload plus
cleanup time was 3.28866 seconds. Peak sampled controller/observed-descendant RSS
was 585,351,168 bytes. The selected bounds were 200 seconds whole, 180 seconds
work, 15 seconds cleanup and 2 GiB sampled RSS. These observations are not a
hard memory/CPU quota or a general performance guarantee.

Actual Guest PID/PGID 11567 was independently observed live and matched the
actual creation journal and required sandbox profile. All nine recorded PIDs
and four actual recorded process groups were independently absent twice after
completion. No sockets remained. An empty temporary home directory remained and
was retained in the residual evidence. This is normal observed-process evidence,
not an exhaustive census of transient children or qualification of cancellation,
uncatchable parent-kill or pre-fsync creation-journal failure paths.

Five full source/runtime/operator map groups were unchanged, including the
47-file scientific packet, 84,917-file common site and 96-file component prefix.
The selected shared SDK, site, runtime and service policy were not modified.

## Manifest, contracts and canonical distribution

The actual normal generator produced the three-node manifest:

`b81cf2a5ae998cd54cd39e3ca9285abbe1349be0b36efdd3b68453d52ca331b1`

It is retained byte-exact. The generator was the accepted
`f929ea628fec11c5cf695a3bee0928866b128050654acc2abf25415c3af9ad2f` tool with
Studio profile data, using actual schema encoding and Python runtime declaration.
It was not a handwritten manifest. The original requirements and tested V2
Python metadata remain unchanged. No signed managed production dependency
closure is selected by this source package.

The selected scientific attempt generated the canonical pair/bundle, replayed
both onto independent pristine copies and detected both deliberately changed
bases with actual canonical `PackPatchError` messages identifying the
`__init__.py` base mismatch. The frozen executed worker required inventory
equality before recording each negative-control result; independently captured
actual-after byte/mode inventories match the exact mutated fixtures. Raw
in-worker **before** inventories were not separately persisted. That limit is
retained; no extra snapshot or unrelated-exception credit is invented.

After the scientific attempt, only this report and two genuine current public
contract files are added. `comfy-api.pyi` is
`42b9ec2d9f7db0190c39fe5207c4253aaf04ec7851a52cb59c6e667a538478a7` and
`comfy-api.d.ts` is
`abf1417d3d2fa5edf993fbf1965c3df4386ea27bf357264bc0588fa5bb5099d2`.
They are reused byte-exact from the published Light contract lineage at
commit `150b7771a0b0931bcd785a3c9e13873ec8ab873c`.

The retained actual generation receipt is
`e65b26f5eb13e4595c0f46a6a135f03371b4b91b94eba5062bdfec1d0d3d0c2a`.
It records canonical producer
`f2bd2165e0d8cb835c3cbc34b0bd1cc0610619b212ad6681ee54d81e39303aaa`,
the same actual f1 SDK, public facade `0fa030498183001898097cddf0983f1167bccc86c753137ec132027b91c6a8db`
and IO source `56fe27bdd63f5e78b9b36b95957d93db1021a955d10a015734cf42ccffc599b6`
as the qualified Studio profile, with actual public/internal class identity.
This is API-source equivalence, not a new qualification of an entire runtime
environment or a generated dependency profile.

The complete Python output parses and declares the public async classmethods
`ImageRef.from_tensor`, `ImageRef.from_value` and `MaskRef.from_value`, without
exposing `_from_raw`. The earlier copied Swap/APZ declaration was stale; it
was not evidence of a missing public SDK operation. No handwritten declaration,
new contract generation, Studio code change or runtime retest was needed.

Canonical metadata-only pair/bundle regeneration and both independent pristine
replays cover the final report/contracts tree without re-running the normal
generator or importing any pack/SDK/science module.

## Evidence and limits

The actual execution archive is 17,374,807 bytes, SHA-256
`e8585a92a554a040d5077739b4b9fdb4a9c032de40096a7a204f20214ebb0ec9`, containing
151 members and 150 verified file pins. It retains the real results, source,
manifest, canonical outputs, argv/environment, profile, journal, live ownership,
maps, controls and retirement evidence. Raw archives remain outside Git.
Compact strict intake and final file-only receipts accompany this source under
`validation/20261020-studio3-native-guest-r2` and
`validation/20261020-studio3-publication-fileonly-r3`.

**No managed-runtime/dependency-profile admission, canonical service identity
adoption, public graph, browser UI, deployed-service or universal whole-pack
acceptance is claimed.** The source publication and any service/registry action
belong to their owners. No new runtime test, native algorithm execution or SDK
change is performed by this documentation/contracts packaging step.
