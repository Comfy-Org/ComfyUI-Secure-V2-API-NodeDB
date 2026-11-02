# Secure conversion report: ComfyUI_bitsandbytes_NF4

- Upstream: `https://github.com/comfyanonymous/ComfyUI_bitsandbytes_NF4`
- Pinned commit: `6c523bf1ee37900757ee538e6683f1312b8f425c` (tree `74a8b10587cd764da8ad76b0322a440538cea790`)
- Status: **converted 0 of 1 declared; 1 registered with a named refusal** (`CheckpointLoaderNF4`)
- Frontend: none (no `WEB_DIRECTORY`). Routes: none.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Every symbol used is also in 0b86765f, so no minimum base applies.

## The node

`CheckpointLoaderNF4` loads a checkpoint whose linear weights are bitsandbytes
4-bit blocks (NF4 or FP4). It builds the diffusion model with bitsandbytes 4-bit
linear layers: the Forge-derived `OPS` in the pristine `__init__.py:14-163`,
installed with `model_options={"custom_operations": OPS}` at `:178`.

Those layers must live inside the host's model loader. A sandboxed pack can only
ask the host for a model through `ModelsDomain.load_checkpoint`, which takes a
closed `weight_dtype` set with no 4-bit option (`_sdk.py:3758-3762`,
`:4084-4115`). It has no custom-operations hook, by design. So v2 cannot load an
NF4 checkpoint, and this is a host capability gap, not a pack issue.

The node stays **registered** with its original id, category, input and three
outputs, so saved workflows open with no missing-node error, and the
`ckpt_name` menu lists the host's checkpoints exactly as the original did. When
queued it **refuses by name**:

- `validate_inputs` returns the refusal, so the prompt fails validation before
  any node runs. Core shows `ckpt_name - <message>`.
- `execute` raises `NF4LoaderUnavailableError` with the same message, in case a
  caller bypasses validation.

Message: "comfyui_bitsandbytes_nf4/CheckpointLoaderNF4 is not yet converted to
Secure Nodes V2: it loads bitsandbytes NF4/FP4 (4-bit) checkpoints, which needs
bitsandbytes 4-bit layers inside the host's model loader, and the Secure Nodes
model loader has no 4-bit option yet. Use a GGUF or FP8 version of the model
with the standard loaders instead."

## API ask

Add host-owned bitsandbytes 4-bit checkpoint loading, as a closed, per-load
option of the existing loader (e.g. `weight_dtype="bnb_4bit"`) or a separate
verb like `load_gguf_model`. The host would own the bitsandbytes dependency,
the 4-bit operations, CUDA placement and the patcher. The guest still passes
only a catalogue name. When it exists, only `execute` changes, and it calls the
verb.

## Parity (tier 1, CPU gate)

`tests/test_comfyui_bitsandbytes_nf4_parity.py`: **REFUSED-AS-DESIGNED**, 81
cases, 30 checks, 2 negative controls detected.
- Pristine and v2 load side by side. The pristine pack imports with the pinned
  bitsandbytes wheel mounted read-only, test only.
- `/object_info` matches the original field for field, through the guest class
  and through the host proxy built from `secure-nodes.json`, including the
  host-filled checkpoint menu.
- The refusal is exact at validate and at execute, and core's queue-time error
  is exact.
- The manifest equals the encoder's output.
- The guest imports only `comfy_api.latest`, and the pristine bytes are
  untouched.

`tests/test_comfyui_bitsandbytes_nf4_guest.py`: the same refusal comes from a
real guest process through core's validation and execution paths.

The original's own execution needs a real NF4 checkpoint (12 GB for Flux) and
targets CUDA. It is in tier 2 (`TIER2.json` in the lane folder).

## Dependencies

Guest: none (`pyproject.toml` `dependencies = []`). `requirements.txt` is the
pristine file, kept byte-identical. The secure runtime never installs from it.

## Known differences

1. The node refuses instead of loading (above). A capability gap, listed as an
   API ask.
2. The Forge 4-bit operations (pristine `__init__.py:14-163`) are not carried
   into v2. They can only work inside the host's loader. The pristine copy stays
   in the pack root.
3. `/object_info` `python_module` is the secure mount path, not the original
   custom_nodes path. A V3 combo also serializes its default
   `multiselect: false`, which the original omits. Neither changes behaviour.
