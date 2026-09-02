# Secure Nodes V2 conversion ledger

Pinned source: `3efceebce982160b18df5a6abcbaf516da2f513d`.

## Exact census

The source registers ten backend node IDs and one frontend extension. This
release supports five backend nodes and rejects five backend nodes plus the
one frontend extension. There are no routes. Pending: 0.

Supported backend IDs: `SenseNovaChat`, `SenseNovaImageGenerate`,
`SenseNovaPromptBuilder`, `SenseNovaVisionURL`, and `SenseNovaVisionImage`.

Rejected backend IDs: `SenseNovaU1LocalLoader`,
`SenseNovaU1LocalTextToImage`, `SenseNovaU1LocalImageEdit`,
`SenseNovaU1LocalInterleave`, and `SenseNovaInterleavePreview`.

Rejected frontend registration: `sensenova.interleave_preview`.

## Supported behavior

The five cloud nodes retain their exact schemas and output order. The pack
still constructs chat and vision messages, normalizes image-size labels, and
uses the byte-identical vendored prompt-builder template. D33's
`integrations.sensenova` domain owns the fixed provider endpoint, host-held
`SN_API_KEY`, request bounds, retries, credential-redacted response projection,
public-HTTPS media download, image decode, and opaque large-text outputs.

Provider text, usage JSON, raw JSON, base64 image text, URL, and image-info
strings remain ordinary downstream STRING values. They are stored behind
host refs during guest execution so a valid multi-megabyte base64 value never
crosses the 1 MiB RPC control channel. `SenseNovaVisionImage` sends only its
host-owned `ImageRef`; PNG conversion happens on the host.

`SenseNovaVisionURL` accepts bounded credential-free HTTP(S) URLs. Its legacy
inline `data:` form is refused because it embeds unbounded binary data in the
workflow/control channel; the adjacent IMAGE-input node is the buffer-safe
equivalent.

## Security rejections

The local loader accepts arbitrary Hugging Face ids, literal filesystem paths,
an optional source checkout path, and GGUF paths, then imports architecture
code from an unpinned `main.tar.gz`. Its returned live Python model is consumed
by the other three local generation nodes. Preserving that authority would
hand the sandbox arbitrary code, paths, model weights, and GPU execution rather
than a fixed model operation. All four are therefore rejected together.

`SenseNovaInterleavePreview` consumes only the rejected local model's custom
result and writes temporary images through ambient paths. Its matching
frontend extension uses parent DOM and raw `/view` URLs. With no supported
producer, both are rejected instead of publishing a dead socket or browser
escape.

The source's import-time `folder_paths` mutation is rejected; V2 does not add
a global `models/gguf` folder for an unavailable loader. `.env` loading and
`SN_BASE_URL` are also rejected: the credential is operator-managed and the
provider origin cannot be redirected to an arbitrary server.

Final backend: 5 supported / 5 rejected / 0 pending.

Final frontend: 0 supported / 1 rejected / 0 pending.

Final non-node runtime behavior: 0 supported / 2 rejected / 0 pending.
