# WAN Ovi trio WSL x86 CPU r1 validation (publication r11)

Scope label: "Ovi trio (OviMMAudioVAELoader, WanVideoEncodeOviAudio, WanVideoDecodeOviAudio), WSL x86 CPU: native CPU, one thread, original vs converted on the default-SDK in-process route at fp32 and bf16; a separate scope from the Mac-bound R6; not Guest, not GPU".

One selected attempt (m_eddd9fd120) of packet wan-ovi-wsl-r1 (5660478, CONFIG 75d1e68d) ran two sequential bounded Linux
containers on WSL CPU: the genuine original nodes, then the registered converted nodes on the default-SDK in-process route (SDK
0d6ec97e, Core 0.37.0). Image e48accf7, Python 3.13.7, torch 2.8.0+cu128, torchaudio 2.8.0; one thread in both roles; uid/gid
1000 with no capabilities, no network, a read-only root and memory = swap = 6 GiB. Checkpoints: mmaudio_vae_16k_bf16 5b60e163 and
the BigVGAN vocoder 22d61314.

COMPARISON fb830923 (exact):
- loader 25/25, encode 43/43 and decode 33/33 pass;
- decode_bf16 is 21/23 and fails: bf16 decode diverges from the original (max_abs 0.287 on the waveform; first visible at the VAE decoder output); cause under investigation.
The taps (decoder and vocoder outputs) are in comparator_inputs/ and in COMPARISON_decode_bf16.json info.

INTAKE_REVIEW.json (29 checks) recomputed every comparison file byte-equal. HASH_BINDING.json: the staged code equals the
tested tree file for file; only the report differs.

Rows: OviMMAudioVAELoader and WanVideoEncodeOviAudio tested; WanVideoDecodeOviAudio tested (scoped: fp32 only), with the bf16
divergence under Known issues. Counts: 133 tested, 10 converted-untested, 4 partial across 147 originals.
