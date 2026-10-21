LoRA Manager rev 8: the Unet Loader GGUF branch (port r1), tested by Tier U test r3 on the a2 base.

Status `PASS_TIER_U` (selection `m_ef88ba99d9`, one attempt, run by MERVYN; 00:52:41-00:53:00Z). The data-only intake (`INTAKE.json`) re-verified the receipt, the bound spec, pins and launcher, the container limits (uid 1000, no capabilities, memory gate) and every result section. No model was built: core's model construction was intercepted on both sides.

What it shows: construction-call parity between the original LoRA Manager GGUF branch (pristine `py/nodes/unet_loader.py` with the pristine ComfyUI-GGUF as its sibling custom node) and the converted node through the real secure Guest path (sandbox off) on 3 GGUF fixtures (one under all 4 `weight_dtype` values), the same refusal with the original wrapper on 2 more, 9 queue-validation names, 4 mutants each caught by its intended check, and the manifest row equal to the backend encoders. `RESULTS_COMPACT.json` has every row; `PORT_NOTES.json` lists the deliberate differences.

Not established: a real GGUF model load or forward, the sandbox, the deployed host (which lacks native ComfyUI-GGUF and the `gguf` package, request #12), LoRA Manager's extra scanner roots, and whole-node certification. Two earlier attempts failed in the test itself (`ATTEMPTS.json`).
