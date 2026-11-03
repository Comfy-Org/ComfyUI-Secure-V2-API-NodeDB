# Secure conversion report: ComfyUI-Frame-Interpolation

- Upstream: `https://github.com/Fannovel16/ComfyUI-Frame-Interpolation`
- Pinned commit: `26545cc2dd95bc3d27f056016300673bdeee78f5` (tree `c1e1afe9e694fdad17b1c3cc1050453c38221844`, 92 files)
- Status: **converted 5 of 16 declared; 11 registered with named refusals.** Two IFRNet checkpoint options are also refused.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used is also in 0b86765f, so no minimum base applies.
- Frontend: none. Routes: none.

## Converted (upstream node bodies, run in the guest)
| Node | Notes |
|---|---|
| RIFE VFI | All 5 checkpoints. Every option is kept (fast_mode, ensemble, scale_factor, dtype, torch_compile, batch_size, states). |
| FILM VFI | `film_net_fp32.pt` runs the pack's own Python `Interpolator` (`vfi_models/film/film_arch.py`) with the TorchScript archive's tensors. No TorchScript is loaded. |
| IFRNet VFI | `IFRNet_S/L_Vimeo90K.pth`. The `*_GoPro.pth` options are refused (404 upstream). |
| Make Interpolation State List | Emits a plain token (below). |
| VFI FloatToInt | Includes the list form. |

Weights: upstream downloaded unpinned, unhashed pickles at run time (`vfi_utils.py:14-40, 80-95`). It unpickled them with `torch.load(weights_only=False)` (RIFE) or `torch.load` (IFRNet), or ran `torch.jit.load` (FILM).
- In v2, every checkpoint is an `sdk.HuggingFaceWeight` with sha256, `on_demand=True` (`_fi_weights.py`).
- Each file is the pinned upstream file converted offline to safetensors by GERALD, in an isolated container, and verified tensor-equal (receipts `GERALD-CONVERSION-RECEIPTS-20261102.jsonl`). RIFE and IFRNet were loaded with `weights_only=True`. FILM is the TorchScript module's state_dict.
- The guest gets tensors only through `models.download_huggingface_weights`, then `assets.resolve`, `digest` and `load_state_dict`.
- **The repo_id/revision are PLACEHOLDERS** for the test runtime. Production hosting is pending Ben.

Boundary edits (all upstream algorithm code is unchanged; `tests/` shows every edit as a diff against pristine):
- package-relative imports instead of upstream's `sys.path` insertion;
- `comfy.model_management` replaced by the pack-local `_fi_device.py` (CUDA if the guest has it, else CPU);
- download helpers replaced by a named `WeightsNotBrokered` refusal;
- the two load lines per node now read the brokered tensors;
- the `config.yaml` read removed (it only named the download folder);
- `film_arch.py`'s cv2 import moved into the one file-path helper that uses it;
- `pyproject.toml` gains `requires-python`.

INTERPOLATION_STATES was a live `InterpolationStateList` object. A value that crosses between guest executions must be plain data, so it travels as `{"frame_indices": [...], "is_skip_list": bool}`. The consumers rebuild upstream's object from it before running upstream code. A malformed token is refused by name.

## Refused (registered with the original schema; named message at validation and at execute)
- **GMFSS Fortuna VFI:**
  - `GMFSS_fortuna_union` needs `rife46.pth`, which is 404 upstream.
  - Both variants run CUDA softsplat kernels through cupy, which a guest cannot run. The non-union weights are already converted, but the kernels are the blocker.
- **AMT, ATM, CAIN, FLAVR, IFUnet, M2M, MOMO, STMFNet, Sepconv VFI:**
  - Their pickles are not converted yet.
  - M2M, STMFNet and Sepconv also need cupy kernels.
  - ATM also needs timm.
  - MOMO also downloads torchvision RAFT weights.
- **KSampler Gradually Adding More Denoise (efficient):** it runs core's sampler step by step inside the node. There is no SDK operation for that. Expanding it into core KSampler nodes would not be exact (per-latent noise).

## Parity (tier 1, CPU gate)
`tests/test_comfyui-frame-interpolation_parity.py`: 150 checks, 0 failed, 4 negative controls detected.
- Pristine and v2 nodes run side by side on the same verified tensors. The pristine side never downloads or unpickles.
- Comparisons use `torch.equal` and type/value equality: RIFE 22 runs, IFRNet 7, FILM 3, State List 10, FloatToInt 7.
- `/object_info` matches field for field for all 16 nodes, through the guest class and through the host proxy.
- Every refusal is exact, including core's queue-time error.
- The manifest equals the encoder's output. The pristine blob ids hold, and untouched files are byte-identical.

`tests/test_comfyui-frame-interpolation_guest.py` runs the host proxy into a real guest:
- RIFE through the guest equals pristine bit for bit;
- the state token is made and consumed in the guest;
- a refused node fails core validation through the guest.

FILM: the pristine node loads TorchScript, which the harness may not do. Two checks cover it:
- The node code runs on both sides with the pack's Python model: EXACT.
- The model is BIT-EXACT to GERALD's TorchScript reference run (max abs 0.0) with one intra-op thread, which is how the reference was produced. GERALD also found eager == TorchScript bit for bit in his isolated converter.
- With two threads, the same gate run differs by up to 6.7e-06 (float32 noise from conv reduction order).

## Dependencies (guest)
torch, numpy, einops, torchvision (`vfi_utils.py` imports), packaging (`vfi_models/rife/__init__.py`). No new wheels; all are in the gate image.

## Known differences
1. FILM: the pack's Python `Interpolator` instead of the TorchScript archive. It is bit-exact on the reference input with one thread. A multi-threaded CPU run can differ in the last float32 bits (up to 6.7e-06 seen); TorchScript itself behaves the same way.
2. INTERPOLATION_STATES travels as a plain token instead of a live object. Only this pack's nodes consume it.
3. Device: the guest uses its own CUDA device, else the CPU. It does not use ComfyUI's device manager, so `--cpu` and MPS flags are not visible to it.
4. V3 output nodes get hidden `prompt`/`extra_pnginfo` automatically (the refused KSampler node). Core fills these; they are not shown.
5. RIFE `torch_compile=True` keeps upstream's `torch.compile` call. It is not exercised in tier 1, because the gate has no C compiler. Where the guest runs, it needs one, as upstream does.
6. `/object_info` `python_module` is the secure mount path.

## Dependency profile (NED profile r1): einops 0.8.2, torchvision 0.23.0
- A production guest sees only its sealed lock, the pack's runtime base and its declared dependency profile, not
  Core's requirements; base 0cd9adec has neither einops nor torchvision.
- Every row loads without them: `secure_nodes.py` imports the upstream modules inside `execute`.
- The converted nodes need both as they run: `vfi_utils.py` imports einops (line 6) and torchvision (line 8) at
  module level, and VFI FloatToInt, Make Interpolation State List and the three VFI models (RIFE, FILM, IFRNet)
  import it.
- `pyproject.toml` pins exactly `einops==0.8.2` (py3-none-any, PyPI sha256
  54058201ac7087911181bfec4af6091bb59380360f069276601256a76af08193) and `torchvision==0.23.0` (cp313
  manylinux_2_28_x86_64, PyPI sha256 a76fafe113b2977be3a21bf78f115438c1f88631d7a87203acb3dd6ae55889e6).
  torch is in the sealed lock, so it is not pinned here (torchvision 0.23.0 requires torch 2.8.0).
- Not covered by this profile: RIFE VFI also imports `packaging` when it runs (`vfi_models/rife/__init__.py:8`).
- `secure-nodes.json` gains `runtime.dependencies.profile_sha256` when the profile is built.
- `tests/test_dependency_profile.py` lets both modules, and the modules the guest bases lack (scipy, torchvision,
  tqdm, yaml, cv2), come only from the pinned copies under /deps.
