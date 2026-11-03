# Secure conversion report: ComfyUI-SeedVR2_VideoUpscaler

- Pinned commit: `4490bd1f482e026674543386bb2a4d176da245b9` (v2.5.24, tree `68c28a545c17c72b8893134006efd0fd32c7e8ce`, 126 files)
- Status: **converted 4 of 4 declared.**
  - SeedVR2VideoUpscaler, SeedVR2LoadDiTModel, SeedVR2LoadVAEModel and SeedVR2TorchCompileSettings, with their original ids.
  - The four GGUF DiT model options are refused by name.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used is also in 0b86765f, so no minimum base applies.
- Frontend: none. Routes: none.

## How it runs
- `secure_seedvr2.py` registers the four nodes with literal schemas (`_seedvr2_schemas.py`).
- Each node runs the pack's own `execute` in the guest. The pack modules are imported inside the node, compatibility module first, as the pack's `__init__.py` does.
- **Torch Compile Settings:** unchanged.
- **DiT and VAE loaders:** unchanged. The executing node id comes from the SDK graph domain (`src/_sn_context.py`), not from `comfy_execution`.
- **Video Upscaler:** before the pack's `execute`, the DiT and VAE checkpoints named in its two config inputs and the pack's two text embeddings are fetched as declared weights. Each has a sha256 and is digest-checked (`src/_sn_weights.py`). Their tensors are then supplied to the pack's loaders.

Boundary edits to pack files (the stage's patch shows each one):
- `src/core/model_loader.py`: the safetensors file read becomes `brokered_state_dict(...)` (twice: direct, and the MPS fallback).
- `src/core/generation_utils.py`: the two embedding file reads become `brokered_tensor(...)`.
- `src/utils/downloads.py`: `download_weight` only checks that the weights were supplied, and `download_with_resume` refuses. A guest never downloads.
- `src/interfaces/dit_model_loader.py`, `vae_model_loader.py`: one import line each.
- `pyproject.toml`: `requires-python`.

Everything else (models, pipeline, color correction, memory management) is the pack's code unchanged.

## Weights
Every safetensors checkpoint in the pack's registry (`src/utils/model_registry.py`) is an on-demand weight declaration with the registry's sha256:
- the six DiT models in folder `diffusion_models`;
- the VAE in folder `vae`.

The pack's text embeddings (`pos_emb.pt`, `neg_emb.pt`) are two required declarations in folder `embeddings`: safetensors files holding the same bf16 tensors, one per file. The pack's own files are never read, so a published snapshot may leave them out.

The GGUF DiT options are refused at validation and at execute, with the same message: the pack's GGUF reader needs a model file on disk, and a guest receives tensors.

## Guest dependencies
The pack imports packages the base guest runtime does not provide. Exact pins, wheel-only:
- diffusers==0.36.0
- omegaconf==2.4.0
- rotary-embedding-torch==0.8.9
- gguf==0.17.1
- opencv-python-headless==4.12.0.88

They must be supplied as the pack's dependency profile.

## Parity (tier 1, CPU)
`tests/test_seedvr2_videoupscaler_parity.py` runs every node on both sides:
- the original pack, which reads checkpoints from disk;
- v2, which receives the same checkpoints' tensors through the SDK.

Both sides take the text embeddings from the declared files; for the original pack only its two `torch.load` calls are redirected. Fixtures are synthetic, and the tests pass with the snapshot's media, example workflows and bundled model files removed.

Coverage:
- **Upscaler:** the full pipeline (VAE encode, one-step DiT, VAE decode, color correction) on tiny CPU fixtures with the default checkpoints, compared with `torch.equal`. Cases: lab, wavelet, adain and none color correction; RGBA input; 5 frames; input and latent noise; uniform batch with prepended frames, `max_resolution` and tensor offload.
- **Config nodes:** the three config nodes' dicts (node id included) and errors are compared exactly.
- **Schema:** `/object_info` is compared field for field for all four nodes. The original's schema is evaluated on a simulated single-GPU host; v2 is checked through the guest class and the host proxy.
- **Integrity:** the manifest equals the encoder's output; the pristine bytes and untouched copies are checked. When the snapshot still has the pack's embedding files, the declared embeddings are checked tensor-equal to them.
- **Negative controls:** perturbed output, embedding, schema and refusal.

`tests/test_seedvr2_videoupscaler_guest.py` runs the config nodes and the GGUF refusal through the host proxy in a real guest process.

## Known differences
1. **Device menus are fixed to a single-CUDA-GPU host:** `cuda:0`, plus `none`/`cpu`/`cuda:0` for offload.
   - The original builds them from the devices it sees, so a multi-GPU or MPS host offers more entries.
   - A CPU-only host fails to build the original's loader schemas at all.
2. **The DiT model menu lists the registry models only.** The original also lists extra model files found on disk.
3. **GGUF DiT models are refused.**
4. **Inside a guest:**
   - there are no ComfyUI progress-bar updates and no mid-run interrupt, because the pack treats both as optional when ComfyUI's modules are absent;
   - the model cache (`cache_model`) lives in the guest process.
5. **Weight integrity is checked by the SDK (declared sha256)** instead of the pack's validation cache. Nothing is downloaded at run time.
   - The text embeddings come from two declared safetensors weights, not from the pack's `pos_emb.pt` / `neg_emb.pt`.
6. `/object_info` `python_module` is the secure mount path.
7. An error raised while a node executes in the guest reaches ComfyUI as a transport error (`WireError`) whose text is the original exception type and message, e.g. the GGUF refusal at execute. Refusals at validation (the DiT loader's GGUF check) are unchanged.
