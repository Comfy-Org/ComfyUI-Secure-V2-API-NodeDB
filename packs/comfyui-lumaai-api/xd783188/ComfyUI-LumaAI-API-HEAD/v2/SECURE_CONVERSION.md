# Secure Nodes V2 conversion ledger

Pinned source: `d783188eeb4664db1e44fd2d897e788a7d2a3d75`.

## Exact census

The source registers 14 backend node IDs and two frontend extensions. This
release supports 13 backend nodes and one frontend extension. It deliberately
rejects `LumaPreviewVideo` and the matching `VideoPreview` frontend extension.
There are no backend routes, startup downloads, schedulers, or other runtime
registrations. Pending: 0.

Supported backend IDs: `LumaAIClient`, `ImgBBUpload`, `LumaText2Video`,
`LumaImage2Video`, `LumaInterpolateGenerations`, `LumaExtendGeneration`,
`Reference`, `ConcatReferences`, `CharacterReference`, `LumaImageGeneration`,
`LumaModifyImage`, `LumaAddAudio2Video`, and `LumaUpscaleGeneration`.

The supported frontend registration is `lumaai.showgenerationid`; the rejected
registration is `VideoPreview`.

## Supported behavior

- `LumaAIClient` produces the same explicit workflow client value. The checked
  in `config.ini` has no key; V2 does not silently acquire process-environment
  secrets when the input is blank.
- ImgBB upload and Luma video/image generation use the D32 fixed-provider
  domains. Pack code still constructs keyframes and reference shapes and keeps
  every source-side validation quirk. The host owns fixed endpoints, bounded
  requests/responses, polling deadlines, public-address checks, redirect
  validation, media decode/download limits, and credential-redacted errors.
- The six source node types with a generation readout keep their disabled
  `gen_output` widget and display `generating...` while they execute.
- Video saves use confined, atomic, new-only output names. Image generations
  keep their JPEG output side effect and IMAGE result through the bounded
  output domain.

The source's duplicate second poll/download in `LumaInterpolateGenerations`
is not repeated: it cannot change the returned value and only duplicates a
paid provider read plus an output overwrite. Existing-output overwrites are
also refused; the secure output contract is new-only.

## Security rejection

`LumaPreviewVideo` accepts an arbitrary string and the legacy frontend assigns
it directly to a browser `<video src>`. That is an ambient browser-network
primitive: it can contact private-network and loopback endpoints from the
user's browser and is not restricted to a URL returned by Luma. The opaque
frontend intentionally has no direct network authority, and no generic URL
proxy is introduced for one pack. The node and its `VideoPreview` extension
are therefore explicit security rejections, not silent no-ops.

Final backend 13 supported / 1 rejected / 0 pending.

Final frontend 1 supported / 1 rejected / 0 pending. Non-node ledger:
0 supported / 0 rejected / 0 pending.
