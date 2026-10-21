calcuis-gguf rev 4 (loader port r6, test r5): actual result of the selected Tier A, B and Q attempts on the "a2 base" (deployed ComfyUI 6257422 plus the undeployed GGML SDK a2 d1a9259, backend a1 894ead3).

Status `PASS_TIER_A`, `PASS_TIER_B`, `PASS_TIER_Q` (selection `m_3482b2024a`, one attempt each, no retry, run by MERVYN under the shared lock). Launcher r3 ran each container as uid 1000 with no capabilities and a memory gate. Every mount was checked against the bound pins before each container was created (`TIER_*_PINS_CHECK.json`). Tier A ran 01:24:59-01:25:14Z, Tier B 01:25:16-01:25:31Z and Tier Q 01:25:33-01:25:46Z; none timed out or hit OOM. The data-only intake (`INTAKE.json`) re-verified every receipt hash, the bound spec, launcher and pins copies, the container limits and every result section.

What revision 4 adds:
- qwen2/qwen3 GGUFs below 65,536 token rows load as a rename with the shipped map. Their keys and bytes equal the original in the Tier A unit rows and in the Tier B construction calls.
- cat GGUFs without a tokenizer file load unchanged. With a tokenizer file beside them, the conversion refuses with its own text, through the real guest-to-host `assets.list`; the original merges the file (keys and the colliding value checked).
- A load-order record (A10, B9): after a gemma3 load the original renames `ffn_norm` differently. The conversion keeps the shipped map. This is listed as a deliberate difference.
- 17 mutants, each caught by its intended check.

Revision 3's evidence was re-run on the revision-4 bytes: 800 bit-exact dequantization cells, construction-call parity for the six loaders, queue validation for all 13 nodes equal to the original lists, and manifest rows equal to the generator encoders. The Guest path ran with the sandbox off, so this is protocol and provider evidence, not sandbox evidence.

Not established: real model or text-encoder construction, load, encode or forward (real qwen2/qwen3 encoders have more than 65,536 token rows and stay refused); LoRA patching; the deployed host; the sandbox; GPU; whole-pack, registry, service or browser use.

Node classes are unchanged: 7 tested (scoped), 6 converted but partly tested (`NODE_CLASSES_PROPOSED.json`). Only the four CLIP loaders reach the changed code (`NODE_CHANGES_REV3_TO_REV4.json`). `v2/SECURE_CONVERSION.md` was refreshed after testing (docs-only); it is the only staged byte that differs from the tested tree. Applying the regenerated pair to a fresh pristine copy re-creates the staged tree exactly. Raw RESULT/stdout/stderr files are retained locally (hashes in `RAW_RESULTS_RETAINED.json`); paths here are workspace-relative.
