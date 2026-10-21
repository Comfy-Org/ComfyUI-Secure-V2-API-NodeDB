# WAN FantasyPortrait r1 validation (publication r10)

`FantasyPortraitModelLoader` and `FantasyPortraitFaceDetector` move from converted-untested to tested. The detector's scope is
in its row: "test env supplies onnxruntime 1.30.0 + opencv 4.12; the converted ONNX profile is unadmitted live, so the detector refuses there" (request #22, PLATFORM_REQUEST_22.md).

One selected attempt (m_e7e741aa2c) of packet wan-portrait-r1 (8f0dcfb7, CONFIG 4e0446cf) ran two sequential bounded Linux
containers on WSL CPU: the genuine original nodes, then the registered converted nodes on the default-SDK in-process route
(SDK 0d6ec97e, Core 0.37.0). Image e48accf7, Python 3.13.7, torch 2.8.0+cu128. Each ran as uid/gid 1000 with no capabilities,
no network, a read-only root and memory = swap = 6 GiB. Both used the trained Wan2_1_FantasyPortrait_fp16.safetensors (1b80e538)
and the ONNX face models bundled in the pack.

COMPARISON 25f14987 (exact): all 90 checks true across two items.
- loader (34): fp16, bf16 and fp32. The recipe is exact and its rebuild repeats it; the adapter is equal tensor by tensor (108)
  and over the 584-key state dict; dtypes are as requested; RNG equal; the rebuild preserves the RNG.
- detector (56): d1 (5 frames, default scales) and d2 (9 frames, non-default scales) give byte-identical embeds, bbox and
  landmarks, with the no-face frame forward-filled. d3 (no face anywhere: TypeError in warp_face_pd_fgc) and d4 (3 frames:
  IndexError in split_audio_adapter_sequence) reproduce the original's own errors.

INTAKE_REVIEW.json (32 checks) recomputed every comparison file byte-equal. HASH_BINDING.json shows that the staged v2 tree
equals the tested tree, file for file.

Live (code-read, not run): the detector stops at `import onnx` with device cpu, or at its CUDA check with the default device
cuda. The loader needs no ONNX package; it has not been run live.
Counts: 130 tested, 13 converted-untested, 4 partial across 147 originals.
