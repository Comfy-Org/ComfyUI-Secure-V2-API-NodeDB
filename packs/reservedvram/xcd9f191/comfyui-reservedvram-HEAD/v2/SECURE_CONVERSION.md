# Secure conversion report: comfyui-reservedvram

- Upstream: `https://github.com/windecay/comfyui-reservedvram`
- Pinned commit: `cd9f1911d960e3d31b3908867c638a19e5d42af3`
- Status: **converted 1 of 1 declared nodes** (`ReservedVRAMSetter`), 0 refused
- Frontend: none. Routes: none.
- SDK: target base 0cd9adec (comfy_api 0.37.0). It uses `io.ComfyNode`, `io.Schema`, `io.Float`, `io.Combo`, `io.Int`,
  `io.Boolean`, `io.AnyType`, `io.Hidden`, `io.NodeOutput`, `sdk.ctx().models.memory_cleanup`,
  `sdk.ctx().system.stats` and `sdk.ctx().graph.block`.
- Permissions: `models.manage` (memory cleanup), `system.stats` (GPU memory reading), `graph.block` (the blocker
  returned when nothing is connected).

## The node

`ReservedVRAMSetter` ("Set Reserved VRAM(GB) ⚙️") is an output node. In the original (pristine `nodes.py`) it:
1. optionally frees GPU memory: `gc.collect()`, `unload_all_models()`, `soft_empty_cache()`;
2. computes a reservation: the manual value, or in `auto` mode the GPU's used memory plus the offset, capped by
   `auto_max_reserved`;
3. sets ComfyUI's `EXTRA_RESERVED_VRAM` to it;
4. returns its optional input, the seed and the computed value. With nothing connected, the first output is
   ComfyUI's `ExecutionBlocker(None)`.

V2 keeps steps 1, 2 and 4 exactly, in the original's order, with the original's console messages:
- **Cleanup.** The three operations run on the host through `models.memory_cleanup`, one call per operation, so the
  order is collect, unload, empty cache, as in the original.
- **GPU memory.** The original reads GPU 0 through NVML, or else `torch.cuda.mem_get_info`. V2 reads the host's
  primary device through `system.stats` and computes `used = total - (free - torch_free)`. Core's free memory is
  `mem_get_info` free plus torch's reserved-but-inactive bytes, so this is exactly `mem_get_info`'s `total - free`.
  A primary device that is not CUDA gives no reading, and both versions fall back to the manual value.
- **Outputs.** The passthrough value comes back unchanged; host handles are the same object. The blocker comes from
  `graph.block(None)`.
- **Fingerprint.** The original's `IS_CHANGED` becomes `fingerprint_inputs`. Seed -1 draws a new seed from the node's
  own time-seeded random state, leaving the global random state untouched; any other seed is returned as it is.

## Parity (tier 1, CPU gate)

`tests/test_reservedvram_parity.py` runs the original and v2 side by side over 6,480 cases:
- device: CPU, and two fake CUDA devices fed to both sides with the same physical numbers (the original through
  `torch.cuda.mem_get_info` and through a fake NVML);
- mode, reserved (-2 to 7), auto_max_reserved, clean_gpu_before, seed (0, 7, -1);
- passthrough values: none, int, str, image, latent, opaque object.
It compares:
- the outputs (identity or blocker; seed; the reserved value's type and float bits);
- the recorded host operations (the same `comfy.model_management` / `gc` functions on both sides);
- the console output;
- that v2's reported request equals the bytes the original assigned to `EXTRA_RESERVED_VRAM`, while v2 leaves it
  untouched;
- `IS_CHANGED` vs `fingerprint_inputs`, and the global random state;
- every declared input option, the outputs, output-node flag, category and display name.
Two negative controls (a perturbed reserved value and a perturbed fingerprint) must turn red.

Result: PASS, 51,867 checks, 0 failed, both controls red.

## Dependencies

Guest: none. `pyproject.toml` declares `dependencies = []`; the original's `nvidia-ml-py` is not needed, because GPU
memory comes from the host. `requirements.txt` is the pristine file, unchanged.

## Known differences

1. **The host's reserved VRAM is not changed.** A sandboxed pack cannot change the host's memory policy, and the SDK
   has no verb for it. V2 computes and returns the same value and prints the original's message, plus one line
   saying the host setting was not changed. Workflow outputs are unaffected; only the host's VRAM headroom differs.
   API ask: a permissioned `models.set_extra_reserved_vram(gb)`.
2. **The memory reading in auto mode** comes from the host's CUDA numbers (`mem_get_info`), the original's fallback.
   The original prefers NVML when it is installed; its device-wide "used" can differ slightly from CUDA's. In both
   versions the value is a live reading and changes from run to run.
3. **One extra console line** (known difference 1).
4. **Hidden inputs:** V3 adds the PROMPT hidden input to every output node.
