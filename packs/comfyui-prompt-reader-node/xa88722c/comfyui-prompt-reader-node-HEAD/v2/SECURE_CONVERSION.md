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

## Removed distribution baggage

The V2 tree excludes the upstream desktop Tk application, update checker,
prebuilt CPython 3.11 wheels, icons/screenshots, CI files, legacy host-importing
node module, and dependency manifests. These are not reachable from the ten
Comfy nodes. The retained parser modules are reachable from the secure entry
and use only Python, Pillow, NumPy, and Torch already present in the managed
runtime.
