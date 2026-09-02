# Secure Nodes V2 conversion ledger

- Pack: `comfyui-ollama`
- Upstream: https://github.com/stavsap/comfyui-ollama
- Pinned commit: `6db7560576e5a59488708e6be13e07b5aba2432a`
- Release: `x6db7560`
- Backend: 9 supported, 0 rejected, 0 pending
- Frontend: 1 supported, 0 rejected, 0 pending

## Intent census

| ID | Intended behavior | V2 status |
|---|---|---|
| `OllamaOptionsV2` | Compose enabled Ollama inference options | supported, pack-side |
| `OllamaConnectivityV2` | Select an allowed Ollama endpoint, model, and keep-alive policy | supported, pack-side configuration |
| `OllamaGenerateV2` | Text/vision generation, thinking, context and metadata chaining | supported through `integrations.ollama.generate` |
| `OllamaSaveContext` | Persist a named token context | supported through confined `output.write_text` |
| `OllamaLoadContext` | Restore a named token context | supported through confined `assets` reads |
| `OllamaChat` | Multi-turn text/vision chat with resettable shared history | supported through `integrations.ollama.chat`; history remains pack-side |
| `OllamaVision` | Deprecated vision generation contract | supported through `integrations.ollama.generate` |
| `OllamaGenerate` | Deprecated simple generation contract and thinking filter | supported through `integrations.ollama.generate`; filtering remains pack-side |
| `OllamaGenerateAdvance` | Deprecated advanced options/context generation | supported through `integrations.ollama.generate`; context remains pack-side |
| `Comfy.OllamaNode` | Discover models, refresh choices, and report connection failures | supported through iframe-safe `comfy.integrations.ollama.listModels` |

## Security boundary

The pack has no Ollama client, HTTP library, backend route, arbitrary fetch,
filesystem path, credential, raw tensor, NumPy, or PIL access. The typed host
broker owns Ollama I/O and bounded IMAGE encoding. Endpoints are limited to
loopback origins or administrator-configured `ollama://` profiles; URLs with
paths, user information, queries, fragments, redirects, or arbitrary hosts are
not accepted. Credentials stay in host configuration and never enter node
inputs, results, logs, or pack code.

The pack still owns prompt construction, the exact option projection, metadata
and context propagation, bounded chat history, and legacy thinking-block
filtering. No node algorithm was moved into the core API.

Saved contexts are JSON text artifacts below `output/ollama_contexts/`. Names
are normalized to a single confined filename. Legacy pack-local PNG metadata
storage was not retained because it granted the node ambient filesystem access;
the pristine pinned snapshot contains no user context files to migrate.
The save input and load output use `OLLAMA_CONTEXT` in V2, repairing the pinned
pack's mismatched `STRING` declarations so these nodes can actually connect to
the generate node whose token contexts they are intended to persist.

## Verification

`backend/tests/test_ollama_pack_conversion.py` proves the exact pristine and V2
censuses, schema and manifest integrity, differential option/filter behavior,
real GuestSession execution for all nine nodes, typed integration call shapes,
IMAGE-ref handling, context persistence, permission and endpoint denial,
frontend worker isolation, patch roundtrip, and cache cleanliness. Actual Ollama
hardware/model inference is the only external boundary not exercised by the
hermetic conversion suite.
