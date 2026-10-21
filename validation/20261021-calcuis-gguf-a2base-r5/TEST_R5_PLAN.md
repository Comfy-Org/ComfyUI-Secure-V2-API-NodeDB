# calcuis-gguf test r5 (for port r6): exact changes from test r4

Base: test r4 (`consumers/ned-calcuis-gguf-differential-20261020-r4`, zip f22e0c49), which passed Tier A/B/Q on port r5.
Port r6 changes only `gguf_state.build_text_table` / `gguf_text_state` and `nodes.text_encoder_state` (+ `tokenizer_pair_absent`);
`STATIC_CHECKS_R6.json` shows the T5 branch, `build_table`, `build_diffusion_table` and the manifest are unchanged.

## fixtures_lib.text_files
| r4 row | r5 row | expect | why |
|---|---|---|---|
| `qwen2_refused`, `qwen3_refused` (token_embd 65536 x 4) | same files | converted-refuses, **new message** `QWEN_BIG_VOCAB_MESSAGE` (65536 rows) | exactly at the threshold: also the killer of the `>` off-by-one mutant |
| `qwen3_small_vocab_narrowing` | `qwen3_small_vocab_rename` | equal; keys = pristine L3 rename | r6 ports the rename-only branch |
| new | `qwen2_small_vocab_rename` (token_embd 2 x 4, blk.0.ffn_norm, blk.0.attn_q_norm, blk.0.attn_output, output.weight, output_norm) | equal | covers the L3 order subtleties (attn_q_norm. before attn_q; attn_output before output.weight) and ffn_norm (the G3 key) |
| new | `qwen3_no_token_rename` (no token_embd) | equal | pig.py checks `token_key in sd` first |
| `cat_refused` | `cat_no_pair_identity` (text_encoders root, no tokenizer file anywhere in it) | equal (identity) | r6 ports pig_work with an empty tokenizer state |
| new | `catpair/text_cat_paired.gguf` + `catpair/tokenizer_cat.safetensors` (2 small tensors, one key colliding with the GGUF) | converted-refuses (`CAT_PAIR_MESSAGE`); the original merges (pair keys win) | the merge stays a platform gap (GERALD_REQUEST §2) |

## Tier A
- `check_text` passes `cat_pair_absent` to `build_text_table` per fixture (True for `cat_no_pair_identity`, False for the paired file); every other row unchanged.
- New A10 load-order row (original only, in process): `load_gguf_clip(qwen2_small)` -> `load_gguf_clip(gemma3_refused)` -> `load_gguf_clip(qwen2_small)`;
  expected: first and third differ only in `blk.0.ffn_norm` -> `post_attention_layernorm` vs `pre_feedforward_layernorm`; the port's table equals the first both times.
  Then `pig.arrays['L3']` is restored to the shipped map (snapshot at import), and every original call in A3/A6 restores it first (single load vs single load).
- A9 mutants (+3): `cat_pair_check_dropped` (nodes.tokenizer_pair_absent returns True) -> killed in Tier B by the paired row; at unit level by A3t if the mutant is applied to build_text_table's guard;
  `qwen_threshold_off_by_one` (`>=` -> `>`) -> killed by A6 `qwen2_refused`/`qwen3_refused` (65536 rows);
  `l3_polluted_with_g3` (`PRISTINE_L3 = {**ARRAYS['L3'], **ARRAYS['G3']}`) -> killed by A3t `qwen2_small_vocab_rename` (ffn_norm).

## Tier B (construction through the Guest, sandbox off)
- New equal rows: ClipLoaderGGUF on `text_qwen2_small_vocab_rename.gguf`, `text_qwen3_small_vocab_rename.gguf`, `text_qwen3_no_token_rename.gguf`, `text_cat_no_pair_identity.gguf`.
- New converted-refuses row: ClipLoaderGGUF on `catpair/text_cat_paired.gguf` (the original merges; the converted refusal text is `CAT_PAIR_MESSAGE`; the pair check runs through the real `assets.list`).
- Every original call already resets GGMLOps dtypes; r5 also restores `pig.arrays['L3']` before each original call; B9 records the load-order pollution once (no reset) as the deliberate difference.

## Tiers Q / T
Unchanged (no validator or CUDA change).

## Records
- PER_NODE_RECORDS: ClipLoaderGGUF/Dual/Triple/Quad labels gain "qwen2/qwen3 below 65536 rows and cat without a pair: tested (construction-call parity)"; the qwen >= 65536 and cat-with-pair refusals keep their GERALD_REQUEST §2 references.
- Deliberate differences: gemma3 L3 mutation (B9/A10 evidence).
