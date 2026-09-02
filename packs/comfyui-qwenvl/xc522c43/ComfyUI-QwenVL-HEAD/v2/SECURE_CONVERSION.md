# Secure Nodes V2 conversion

This sibling converts the pinned upstream commit
`c522c43b15618a4d5c92b2500105ee2a65527f95` without changing the pristine
tree beside it.

## Behavior boundary

The six upstream backend IDs remain present. Prompt presets and overrides,
uniform video-frame selection, prompt-enhancer style composition, response
cleanup, planning detection, the single constrained retry, and optional
English translation remain pack code.

Model files and model execution remain host-owned. The pack declares a closed
catalogue of public Hugging Face weight files with immutable revisions and
SHA-256 pins. They are installed atomically on first selection and reused from
the verified host cache. The guest never receives a weight path, network
client, tokenizer, model object, device object, or raw image tensor.

The canonical Qwen path accepts only SafeTensors shards for known Qwen
families. The llama.cpp path accepts only the declared GGUF model/mmproj
pairs. The unsafe upstream mechanisms—runtime `snapshot_download`, runtime
`hf_hub_download`, `trust_remote_code=True`, arbitrary `custom_models.json`
repositories, arbitrary filesystem paths, and optional Python runtime
imports—are absent from active V2 code. Arbitrary custom repositories are the
one deliberately rejected compatibility behavior: an unreviewed repository
cannot add executable model configuration or undeclared weights to a sealed
pack. Adding a model safely requires a new pinned pack release.

Legacy attention-backend and `torch.compile` controls are accepted in their
original schemas as compatibility hints. The secure host owns kernel choice,
compilation, quantization support, and memory policy; no low-level device or
module authority crosses into the guest. For canonical SafeTensors models,
`cpu` remains an explicit placement request while `auto`, `mps`, `cuda`, and
`cuda:N` all map to the host-owned accelerated `default` policy. This is a
placement-policy compatibility change, not a rejected model behavior. The
closed llama.cpp vendor integration can honor its reviewed device spellings
directly.

Canonical Qwen configuration, tokenizer vocabulary, chat templates, image and
video preprocessing, MRoPE/timestamp construction, shard merge rules, and
official block-FP8 dequantization are static host code. They are never fetched
as remote configuration or executed from a model repository.

## Frontend

`QwenVL.appearance` uses only `/comfy/api/v2.js`. It preserves the six active
nodes' foreground colors, background colors, and initial width through the
published node facade. It has no parent DOM, renderer internals, network, or
legacy `/scripts/app.js` access. The stale appearance entry for the absent
`AILab_QwenVL_PromptLibrary` node is intentionally omitted.
