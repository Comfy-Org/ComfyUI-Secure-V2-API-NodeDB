# Ovi bf16 decoder divergence: ranked write-up and the decisive cross test (source-only)

## Established (wan-ovi-wsl-r1, COMPARISON fb830923; static reads)
1. Code: the vendored VAE (vae.py, vae_modules.py, edm2_utils.py, distributions.py), BigVGAN (models.py, activations.py,
   alias_free_torch/*) and mel_converter.py in the converted `_owned_ovi` are byte-identical to the original `Ovi/`. Only the glue
   differs: async constructors (features.py, autoencoder.py, bigvgan.py), the digest-bound weight read (weights.py), and the
   runtime/node wrappers (secure_ovi_runtime.py, secure_ovi_nodes.py).
2. State: the bf16 model is bitwise equal on both sides (l16: every parameter and buffer, requires_grad, module repr, dtype).
   The inputs, recipe and RNG are equal.
3. Numeric environment: equal on both sides, the converted one also inside a dispatch scope. This covers threads 1, interop threads,
   oneDNN/MKL flags, float32 matmul precision, determinism, CPU capability AVX512, default dtype, the parallel_info digest and the
   thread env vars.
4. fp32 is bit-exact (decoder output and waveform). bf16 differs from the VAE decoder output onward: 3,551/5,120 values, max_abs
   0.047 on a 4.78 peak, i.e. 1-2 bf16 ulps. The vocoder amplifies it to max_abs 0.287 on the waveform. Each side is
   repeat-identical.
5. The same numbers appeared in ovi-a (2026-10-15: an older tree, the live engine venv, the old profile). In both runs the
   "original" process imported the original pack and the "converted" process the converted pack. Code path and import environment
   are confounded.
6. The in-process backend awaits the node on the same thread, with no autocast or inference-mode wrapper (_sdk.py
   InProcessExecutionBackend.dispatch). Neither pack nor Core monkeypatches torch functions.
7. The import environments differ. The converted role had converted-site on sys.path: opencv-python-headless (with its bundled
   native libs), matplotlib, kiwisolver, contourpy, fontTools. The original role did not, and it built a PromptServer.

## Ranked hypotheses
1. **Process state from the import environment (most likely).** A native library or setting loaded by one role's import closure
   changes how bf16 kernels execute, while fp32 kernels are unaffected. Candidates: the opencv/matplotlib native libs on the
   converted side, or a Core/server import on the original side. Why ranked first: facts 1-4 and 6 leave no code or state
   difference; the effect is bf16-only, which points at bf16-specific kernel paths (oneDNN bf16 conv/brgemm, bf16 elementwise
   conversions); and 7 is a concrete process-level difference.
   - Fix direction: if the converted pack's import closure loads such a library where the original does not, import it lazily
     there. If the original's own production environment also loads it (opencv is common in ComfyUI installs), the reference
     environment is the one to fix (mount the same libraries in both roles). Either way bf16 becomes exact without touching the
     vendored math.
2. **An object difference the state digest cannot see.** Strides, storage offsets, alignment, the inference-tensor flag, or plain
   module attributes could differ between the two constructions (for example a parameter left non-contiguous after the bf16 cast).
   oneDNN then picks a different bf16 weight reorder or kernel, while fp32 goes through ATen paths that normalize layout.
   - Fix direction: make the converted construction produce the original's layouts (same cast order, `.contiguous()` where the
     original's tensors are dense).
3. **Thread-local or allocation-dependent state** (MXCSR flush-to-zero, OpenMP ICVs, pointer alignment), set differently in the
   two processes. Unlikely: everything runs on the main thread, one thread, through 64-byte-aligned allocations. Denormal flushing
   would not explain 69% of values differing.
4. **A hidden autocast or grad/inference context in one route.** Unlikely per fact 6, but the cross test records the autocast state
   per stage anyway.

## The decisive test (this packet; no run until selected)
One container (role "cross") mounts both trees. One interpreter, one thread:
- S0, minimal: Core + SDK + PromptServer. The original Ovi modules (namespace over /original/wan_original) and the converted Ovi
  modules (namespace over /candidate/<pkg>) are imported without either package __init__. orig_model is built by the original
  loader; conv_model by the converted loader + rebuild_ovi in an SDK dispatch.
- S1: import the full original package (converted-site NOT on sys.path), as the original role did.
- S2: add converted-site and import the full converted package, as the converted role did.
- Each stage runs the VAE decoder on the same bf16 latent, for both models, outside and inside an SDK dispatch scope, twice each.
  Recorded per run: a per-submodule forward trace (input/output digest, dtype, strides) and the oneDNN verbose summary
  (implementation, memory descriptors, shapes). Recorded per stage: an extended environment (SDP flags, CPU autocast, a denormal
  probe, the torch config digest) and the shared libraries newly mapped.
- At S2 the full nodes run as well: the original decode on orig_model, and the converted node (its own rebuild) through dispatch.
- Model dumps compare strides, offsets, alignment, inference flags and plain attributes for both models.
- Every output is classified against the run references: run-original 8616d26a, run-converted 01f0d913 (decoder tap); waveforms
  c31fc291 / 11fc9643.
Verdicts (DIAGNOSIS.json):
- CODE_OR_OBJECT if the two models differ inside one stage (hypothesis 2; the first split names the module, and whether its input
  was still equal);
- IMPORT_EFFECT_<stage> if a stage transition changes both models (hypothesis 1; libs_new names the libraries);
- PROCESS_STATE if they agree everywhere (then the run difference came from role state outside these stages, and the
  classification shows which role's environment the cross matches).
Cap: memory = swap = 6 GiB, stop 5.5 GiB, gate 10 GiB, 600 s, one thread, no retry. Expected about 1-2 min and 2-3 GiB.
