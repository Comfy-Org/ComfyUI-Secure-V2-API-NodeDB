# GERALD request d4ddc2de, section 2, revision 2 (calcuis-gguf port r6)

This replaces section 2 of `consumers/ned-calcuis-gguf-census-20261020-r1/GERALD_REQUEST.md`. Sections 1 and 3 are
unchanged. Route: MERVYN re-sends it to GERALD (plan `coordination/CALCUIS_GGUF_R6_PLAN_20261020.json`).

Changes from r1:
- Two concrete asks: a per-entry float16 dequantize option, and a merge of several state refs for one encoder.
- A correction: dog gets its vision tensors from the same file, not from a pair.
- What port r6 now loads without platform help.

## 2. Text-encoder transforms that a byte-range table cannot express

`assets.gguf_tensor_state` maps names to file byte ranges. Renames work that way; data transforms do not, and the
provider does no host-side transforms. The transforms below are in `pig.py load_gguf_clip` (lines 488-546, calcuis/gguf cb433968).

- **t5/t5encoder with a token_embd of (256384, 4096|768):** builds `spiece_model` from GGUF tokenizer metadata (`tokenizer_builder`).
- **llama, qwen2, qwen3, qwen2vl, qwen3vl, mistral3, gemma3, dog:**
  - A token_embd with at least 65536 rows is dequantized to fp16 (pig.py:501, 506).
    **Ask:** a per-entry table option, for example `"dequantize": "float16"`, applied host-side exactly as
    `dequantize_tensor(dtype=torch.float16)` at pig.py:506. With it, real-size qwen2/qwen3 become a guest-side L3 rename plus
    this option on token_embd. Port r6 already loads them below 65,536 rows.
  - For token_embd with at least 65536 rows, `tekken_model` (llama 131072x5120, mistral3 131072x3072) or `spiece_model`
    (gemma3) is built from metadata.
  - llama/mistral3 q/k rows are permuted with n_head 32 and n_kv 8 (`llama_permute`, on the packed tensor data).
  - gemma3 norm weights are dequantized, then 1.0 is subtracted (`gemma_norm`).
- **qwen2vl, qwen3vl:** vision tensors are merged from a paired `*mmproj*.gguf` (`find_mmproj_pair`), then dequantized, with
  qkv concatenated and patch_embd stacked.
- **dog:** takes its vision tensors from the same file (`handle_visual_tensor(path)`, pig.py:519-521), not from a pair.
- **gemma2:** `spiece_model` is built and renames are applied.
- **ideogram/ideogram4:** every quantized tensor is dequantized to fp16.
- **cat:** the first `*tokenizer*.safetensors` in the GGUF's own directory (`gguf_connector/mmj.py find_tokenzier_pair`) is
  merged with `sd.update`, so pair keys win on a collision.
  **Ask:** either several state refs per encoder in `ggml_text_encoders_from_state_dicts`, merged host-side in order, or a
  host merge verb.
  Port rule once that exists: refuse when more than one tokenizer file matches. The original takes the first match in
  `os.listdir` order, which is not deterministic.
  Port r6 loads cat GGUFs unchanged when there is no pair. It refuses when the host listing shows a possible pair in the
  same relative directory under any text_encoders root.
- **cow:** tokenizer tensors are cast to uint8.

General ask: host-side support, for example transform descriptors in the gguf-tensor-table or constructor options. A bounded
route for guest-computed tensors does not scale, because fp16 token embeddings reach about 1 GB.

FYI, no ask: pig.py:507-509 writes the G3 map into the shared `arrays['L3']` on every gemma3 load. Because of that, later
llama-family loads in the same process rename `ffn_norm` to `pre_feedforward_layernorm`. The port always uses the shipped L3
map, which gives the original's result in a fresh process. This is recorded as a deliberate difference (test r5: Tier A A10,
Tier B B9).
