# Secure Nodes V2 conversion ledger

- Pack: `comfyui-ollama-describer`
- Upstream: `https://github.com/alisson-anjos/ComfyUI-Ollama-Describer`
- Pinned commit: `43e9c128ce31b83194d6f8ba87dbc1dd158bd59d`
- Release key: `x43e9c12`
- Pristine census: 26 tracked files, preserved byte-for-byte outside `v2/`
- Pristine digest: `485d3904eeab99634cd0cc6ccd55498fb9792fce126a42e8573e1fbd9d63d1f6`
- Declared weights: none
- Frozen Python stub: `9fa75d099086e25a456aad642306fd8d12a5d8f3d1a090b45393018a5b8258a8`
- Frozen TypeScript stub: `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`

The current implementation keeps prompt construction, text transformation,
JSON selection, directory iteration, caption formatting, frame selection, tool
aggregation, and the bounded agent loop in the pack. The host owns Ollama and
web transports, managed assets and output, image decoding, credentials, and
all frontend DOM. No node-supplied Ollama model is downloaded automatically;
an administrator must install it once outside node execution.

## Backend census

| Node ID | Status | Intended behavior / disposition |
| --- | --- | --- |
| `OllamaCaptionerExtraOptions` | supported | Build the selected pack-owned caption-instruction list. |
| `OllamaImageCaptioner` | supported | Iterate a managed input prefix, decode images through `assets.load_image`, build prompts pack-side, call bounded Ollama generation, and write named captions beneath managed output. An empty `output_dir` mirrors the input prefix beneath output instead of mutating input. |
| `OllamaImageDescriber` | supported | Generate from a managed `ImageRef`, including bounded JSON Schema output and timeout. |
| `OllamaTextDescriber` | supported | Bounded Ollama text generation, including JSON Schema output and timeout. |
| `TextTransformer` | supported | Unescape, prepend, append, and literal/regex replace locally. |
| `InputText` | supported | Pass through the schema's `string` input. This fixes the pristine node's `string`/`text` argument mismatch according to its clear intent. |
| `JsonPropertyExtractorNode` | supported | Parse bounded JSON and traverse a dotted object-property path locally. |
| `OllamaVideoDescriber` | supported | Select a bounded stride/cap of opaque video frames pack-side, then generate through the bounded Ollama image broker; the 4096-token source default is supported. |
| `OllamaToolCombine` | supported | Aggregate up to 16 plain tool descriptors locally. |
| `OllamaTool_WebSearch` | supported | Emit a plain bounded tool descriptor without the workflow credential; the agent invokes generic host-profile DuckDuckGo or Ollama web search and formats results pack-side. |
| `OllamaAgent` | supported | Run the complete bounded ten-iteration loop pack-side over generic tool-call chat, including assistant tool-call and tool-result history, multiple ordered calls, thinking text, unknown/error results, and a terminal iteration cap. |
| `OllamaTool_FileSearch` | security-rejected | Its behavior is to let model output choose and read an arbitrary ambient local path. That authority must never be granted. |
| `OllamaTool_PythonCode` | security-rejected | Its behavior is arbitrary supplied Python/import execution with connected workflow objects in globals. That authority must never be granted. |

Backend tally: 11 supported, 0 pending, 2 security-rejected.

Automatic `client.pull(model)` is a separately rejected side effect, not a
node rejection. Secure automatic weights may come only from pinned Hugging
Face declarations and this pack declares none.

## Frontend census

| Registration | Status | Intended behavior / disposition |
| --- | --- | --- |
| `OllamaDescriber.HelpPopup` | supported | A V2 node-menu action opens the description in a host-owned, text-only dialog; it replaces LiteGraph painting, hit testing, and document-global listeners. |
| `OllamaDescriber.ApiKeyMask` | supported by secure replacement | The obsolete workflow API-key widget is hidden declaratively. Ollama web-search credentials are host-profile-owned and never enter the workflow or guest, so password presentation is no longer needed. |

Frontend tally: 2 supported, 0 pending, 0 rejected.

## Shared contracts used

1. Generic cross-vendor tool-call chat accepts ordinary system/user,
   assistant-with-tool-calls, and tool-result messages and returns bounded
   assistant tool calls. The ten-iteration loop remains here.
2. Generic host-profile web search returns bounded
   `{title, url, snippet}` records. Search-result formatting remains here.
3. The Ollama vendor integration supplies managed-image generation, bounded
   JSON Schema responses and timeouts, closed generation options, and a
   `num_predict` ceiling that includes the node's 4096-token video default.

Pending API gaps: none.

There are no whole-node rejections beyond the two behaviors above and no
complex node algorithm has been moved into core.
