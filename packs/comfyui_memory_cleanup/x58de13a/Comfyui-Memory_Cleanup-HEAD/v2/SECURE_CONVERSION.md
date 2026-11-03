# Secure conversion report: Comfyui-Memory_Cleanup

- Upstream: `https://github.com/LAOGOU-666/Comfyui-Memory_Cleanup`
- Pinned commit: `58de13a6090e04408e343501ff8902c034d9f518` (tree `03d019f75cfc1ecc39abbbcd70236aff33a0c00d`)
- Status: **converted 2 of 2 declared nodes** (`VRAMCleanup`, `RAMCleanup`), 0 refused
- Frontend: none. Routes: none.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used (`io.ComfyNode`, `io.Schema`, `io.Boolean`, `io.Int`,
  `io.AnyType`, `io.Hidden`, `io.NodeOutput`, `sdk.ctx().models.memory_cleanup`) is also in 0b86765f, so no minimum base
  applies.

## The nodes

Both nodes are output nodes that return their optional `anything` input unchanged, so they can sit anywhere in a graph to
trigger a cleanup. Host handles (tensors, latents, models and other opaque objects) come back as the very same object.
Plain JSON-like values (numbers, strings, lists, dicts) cross the sandbox boundary by value, so they come back equal
but as new objects. Both keep the original `IS_CHANGED`, which returns the current time, as
`fingerprint_inputs`. They re-execute on every queue, and so does everything downstream of them, exactly as before.

### VRAMCleanup (`🎈VRAM-Cleanup`)

The original calls `comfy.model_management.unload_all_models()` when `offload_model` is on. When `offload_cache` is on
it then calls `gc.collect()`, `comfy.model_management.soft_empty_cache()` and the prompt queue's `free_memory` flag
(pristine `__init__.py:48-63`).

V2 asks the host for the same operations, in the same order, through the public SDK verb
`models.memory_cleanup(empty_cache, collect_cycles, unload_all_models)`, with permission `models.manage`. It makes one
call per operation, so the order is unload, then collect, then empty cache. Errors are swallowed and reported on the
console, as in the original.

### RAMCleanup (`🎈RAM-Cleanup`)

The original trims the operating system's file cache and the working sets of host processes through ctypes and psutil,
then sleeps one second per retry and prints the RAM usage it measured (pristine `__init__.py:106-152`). A sandboxed pack
cannot touch host processes or the host OS, so V2 passes the value through and prints that the trim was skipped.

## Parity (tier 1, CPU gate)

`tests/test_comfyui_memory_cleanup_parity.py` runs the original and v2 side by side:
- VRAMCleanup: 36 input combinations × 3 checks.
- RAMCleanup: 72 input combinations × 2 checks.
- Interface and fingerprint checks.

It compares:
- the returned object (identity, for nine value kinds including tensors and opaque objects);
- the sequence of host memory operations actually performed (recorded on the same `comfy.model_management` and `gc`
  functions on both sides);
- the console message;
- every declared input option;
- the outputs, output-node flag, category and display names;
- `IS_CHANGED` vs `fingerprint_inputs` on a frozen clock.

Two negative controls (a perturbed output and a perturbed fingerprint) must turn red.

## Dependencies

Guest: none (`pyproject.toml`: `dependencies = []`; the original's `psutil` is not needed). `requirements.txt` is the
pristine file, unchanged.

## Known differences

1. VRAMCleanup does not set the prompt queue's `free_memory` flag; a guest has no PromptServer. The explicit unload,
   collect and empty-cache operations still run on the host.
2. RAMCleanup performs no OS-level memory trimming and no per-retry sleeps; its console message reports the skip
   instead of RAM usage. The returned value is unchanged.
3. V3 adds the `prompt` hidden input to output nodes; the original declares `unique_id` and `extra_pnginfo` only.
   Behaviour is unchanged.
4. Plain values (numbers, strings, lists, dicts) pass through equal but as new objects (sandbox boundary). This
   matters only to code that mutates the value in place or compares identity.
5. If the host runtime has not granted `models.manage`, the memory-cleanup request is a no-op on the host, while the
   node still prints its completion message (as the original does after any attempt).
