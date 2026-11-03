# SD Prompt Reader — Secure Nodes V2 conversion

Pinned source: `receyuki/comfyui-prompt-reader-node` at
`a88722ce8fe081be83d7fddb2ebe88f616b14662` (including the pinned
`stable-diffusion-prompt-reader` parser submodule at
`1a499becb0a88fd28ac3e4e09bd8917ce95c9629`).

## Census and disposition

- Backend nodes: **10 supported / 0 rejected / 0 pending**.
- Frontend registrations: **5 supported / 0 rejected / 0 pending**.
- Other Comfy runtime behavior: **0 supported / 1 rejected / 0 pending**.

The ten backend identities are `SDPromptReader`, `SDPromptSaver`,
`SDParameterGenerator`, `SDPromptMerger`, `SDTypeConverter`,
`SDAnyConverter`, `SDBatchLoader`, `SDParameterExtractor`, `SDLoraLoader`,
and `SDLoraSelector`. The five frontend identities retain the prompt,
parameter, extractor, and batch readouts plus the seed controls through the
opaque V2 facade.

The sole rejected behavior is the package entry point deleting another
directory under ComfyUI's global `web/extensions` tree at import time. That is
package-manager mutation, not node behavior, and no sandboxed pack may perform
it. V2 owns only its declared `WEB_DIRECTORY`.

## Boundaries

- Prompt Reader reads only a selected managed `input` asset, and its pixels
  cross only under `raw`. The vendored multi-tool metadata parser remains
  pack-side; it has no updater, desktop GUI, network, or general file access.
- Batch Loader lists only a selected directory inside managed `input` (or a
  bounded explicit list of managed image names). An arbitrary host path is
  deliberately not interpreted.
- Prompt Saver delegates encoding, workflow metadata, collision-safe writes,
  and A1111-compatible metadata to `output.save_images`. Model, VAE, LoRA, and
  embedding hashes come from managed catalogues through `assets.digest`.
  Its `FILE_PATH` result is the logical managed output name rather than a host
  absolute path.
- Parameter Generator uses the host-owned checkpoint/VAE loaders. Its explicit
  legacy config option is the closed D31 loader argument; YAML and weights do
  not cross into the guest.
- LoRA Loader resolves one managed LoRA asset and applies it through the
  existing opaque model operation. Model and CLIP internals remain host-owned.

Permissions are therefore limited per node to combinations of `assets`,
`raw`, `output`, and `models`. The five pure conversion/orchestration nodes need
no authority.

## Generator and LoRA selector outputs

Parameter Generator returns Core's sampler and scheduler lists as the types
of its `SAMPLER_NAME` and `SCHEDULER` outputs. V2 declares each as a COMBO
output whose options are exactly that list (`_secure_runtime.py`,
`_output`). A Core that reports a COMBO output's declared options as its type
then validates a link into a list-typed input, such as KSampler's
`sampler_name` and `scheduler`, as it does for the original: the lists must
share a choice. A Core that reports every COMBO output as the plain string
`COMBO` refuses those links (return type mismatch). The pack cannot change
that.

These two lists, like the sampler and scheduler menus, are frozen copies of
Core's lists in `_schemas.json`. `tests/refreeze_core_lists.py` refreshes
them from the original running on the deployment Core. It only adds choices
that the newer Core provides. Choices that other installed packs add to
Core's lists at runtime, such as extra schedulers, are not mirrored.

In the original, `MODEL_NAME` and `VAE_NAME` (Parameter Generator) and
`LORA_NAME` (LoRA Selector) take the host's model-folder lists as their
types. Those lists belong to the host, so V2 declares these outputs with no
options, and Core serves them as a generic `COMBO`. They still link into
this pack's own inputs, such as the Prompt Saver's `model_name` and the Type
Converter's inputs. A link from one of them into a Core input that lists
model files, such as a checkpoint loader's `ckpt_name`, is refused, while
the original accepts it.

## Removed distribution baggage

The V2 tree excludes the upstream desktop Tk application, update checker,
prebuilt CPython 3.11 wheels, icons/screenshots, CI files, legacy host-importing
node module, and dependency manifests. These are not reachable from the ten
Comfy nodes. The retained parser modules are reachable from the secure entry
and use only Python, Pillow, NumPy, and Torch already present in the managed
runtime.

## Verification

`tests/test_combo_outputs.py` compares the original with the served V2 nodes
on CPU without weights. It covers:

- loading the manifest with the real loader;
- every node's object_info outputs;
- Core's prompt validation with generator links into KSampler and into this
  pack's nodes, including refused controls;
- values returned by a real guest.

`tests/encode_manifest.py` regenerates `secure-nodes.json` with the live
encoder and loads it with the real loader.
