# WAN Qwen 3B Linux CPU r4 validation (publication r7)

QwenLoader and WanVideoPromptExtender move from converted-untested to tested with this exact scope:
"native CPU bf16, original vs converted on the default-SDK in-process route, deployed engine SDK 0d6ec97e (Core 0.37.0), 3 seeded 12-token cases; not Guest, not GPU, not 7B".

One selected attempt (m_556a1fc2ad) of packet wan-qwen3b-linux-cpu-r4 ran as two sequential bounded Linux containers on WSL
CPU. Each was uid/gid 1000 with no capabilities, no network, a read-only root and memory = swap = 11 GiB. It compared the
genuine original nodes against the converted nodes on the default-SDK in-process route (deployed engine SDK 0d6ec97e, Core
0.37.0). Both used the same cached 3B bf16 checkpoint. COMPARISON 85a854de has all 14 exact checks true and all 6 negative
controls detected: 434 parameters + 1 buffer bitwise equal, tied lm_head, tokenizer, recipe, RNG, and identical generated
text in 3 seeded 12-token cases. The packet and deps trees were re-verified before each role. An independent intake
(INTAKE_REVIEW.json) recomputed the comparison byte-equal from the role observations.

Environment: image 862ab95d (native-validation r1), Python 3.13.7, torch 2.8.0+cu128, transformers 4.50.3. accelerate 1.13.0
and gguf 0.19.0 came from exact PyPI wheels, unpacked read-only (DEPS_PROVENANCE.json); nothing was installed or built. Only
v2/SECURE_CONVERSION.md changes in the corpus. The exercised original and converted files equal corpus main 2abc76c4 by Git
blob. Not claimed: Guest, GPU, 7B, fp16/fp32, long system prompts, UI/registry, installed runtime, whole pack.
Counts: 128 tested, 15 untested, 4 partial across 147 originals; 146 manifest declarations unchanged.
