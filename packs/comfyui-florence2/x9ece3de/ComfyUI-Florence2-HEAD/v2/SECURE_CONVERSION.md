# Secure Nodes 2.0 conversion

Pack: `comfyui-florence2` (`ComfyUI-Florence2-HEAD`).

Upstream: https://github.com/kijai/ComfyUI-Florence2

Pinned upstream commit: `9ece3de914214c5f581d725167bc9d0eeb0d1120`
(release key `x9ece3de`, v1.1.0). The 15-file pristine tree is byte-for-byte
equal to GitHub's archive for that commit; the archive SHA-256 observed during
conversion was
`c87b2503ba68a7031de00369f867e4e013def950906e3bbc090076f2d6f1f82d`.

- Backend: 4 supported, 0 rejected, 0 pending.
- Frontend: 0 supported, 0 rejected, 0 pending. The pack ships no `web/`, no
  `WEB_DIRECTORY`, and no JavaScript; there is no browser surface to port.

Terminal backend ledger:

- `DownloadAndLoadFlorence2Model` — supported.
- `DownloadAndLoadFlorence2Lora` — supported.
- `Florence2ModelLoader` — supported.
- `Florence2Run` — supported.

## Where Florence-2 runs

Core's guest model domain is a closed whitelist and none of its loaders can
build this architecture. Extending it was rejected: Florence-2 is one model
family, and bending a canonical loader around it would put a large amount of
vendor model code in core. The Impact Subpack arrangement is used instead —
architecture, tokenizer, prompt construction, the generation loop and every
line of parsing and drawing stay inside the isolated pack, and core brokers
only two things: installing a declared weight file, and handing over its
tensors. **This conversion needed no new core API.**

## What changed at the boundary

- `snapshot_download(repo_id=...)` is gone. It fetched an entire repository,
  unpinned, whatever it contained that day — including `pytorch_model.bin`
  pickles. Every weight this pack can fetch is now named in
  `_florence2_catalog.py` at a fixed repository revision as a single
  SafeTensors file with its SHA-256 recorded: 14 models plus 1 LoRA adapter.
  The host refuses any request that is not byte-for-byte one of those
  declarations, verifies the digest after download, and serves later requests
  from its cache. All are `on_demand`, so selecting one model installs one
  file. On 2026-08-31 all fifteen declarations were checked against the
  immutable revision and LFS object metadata returned by the Hugging Face Hub;
  every revision resolved exactly and every object digest matched.
- `trust_remote_code=True` does not appear at this commit and none is
  reintroduced. Upstream itself removed `transformers` in `9acc6e9`
  ("Re-implement whole model natively") and vendored `model/`; this conversion
  keeps that vendored code, pinned to the same commit as the rest of the pack,
  with the host imports replaced by `model/_ops.py`.
- The tokenizer is no longer read out of a downloaded snapshot. `tokenizer.json`
  is vendored into `model/`, covered by the pack manifest, and checked against
  a recorded SHA-256 before use. One file serves every supported model: across
  all fourteen repositories the BPE vocabulary (50265 entries) and merge table
  are identical, and the only difference is the 1024 Florence-2 special tokens,
  which `Florence2Tokenizer._add_special_tokens` appends in the same order for
  the same ids 50265..51288 — exactly the embedding table's 51289 rows. This
  was verified id-for-id against five repositories spanning every tokenizer
  serialization found in the set. The one genuine extra, Castollux's
  `<image>`, is declared in `EXTRA_SPECIAL_TOKENS` and passed through.
- `config.json` is never fetched. `Florence2Config.from_state_dict` derives the
  architecture from the checkpoint's own tensor shapes, so the weights are
  self-describing and no repository config file is needed.
- `folder_paths`, `comfy.ops`, `comfy.model_patcher`, `comfy.model_management`
  and `comfy.utils` are gone, along with the module-scope `os.makedirs` and
  `folder_paths.add_model_folder_path("LLM", ...)` that ran on import.
- `Florence2ModelLoader` listed `models/LLM` from inside `INPUT_TYPES`, which
  runs in the host process. It now uses a remote combo served by the host's
  own model route plus a host-safe `validate_inputs`, and resolves the
  selection through the asset broker at execution. The node never builds a
  path.
- `DownloadAndLoadFlorence2Lora` returned a filesystem path as its `PEFTLORA`
  output. It now returns a logical catalogue name, which carries the same
  meaning and is not a path.
- `FL2MODEL` was a live `ModelPatcher` plus a `Processor`. It is now a
  plain-data descriptor naming the declared weight, precision and adapter;
  `Florence2Run` re-derives the model from it. Nothing live crosses the wire.
  Both the model and LoRA descriptor are closed records. Downloaded descriptors
  must reproduce a declaration exactly, and local descriptors are confined to
  a safe logical name in `text_encoders`; injected folders, traversal names,
  repository identities, tokenizer extensions and adapter metadata are
  refused before an asset request.
- `apply_florence2_lora` used `comfy.lora` and `ModelPatcher.add_patches`.
  It now does the same arithmetic directly on the parameters —
  `weight += strength * (alpha / rank) * (up @ down)` in float32, rank read
  from the adapter's own `lora_down` shape — which is what ComfyUI's LoRA
  weight adapter computes. Differentially tested against core's real
  `comfy.weight_adapter` output.
- Progress is published through the brokered progress channel from the node's
  image loop, exactly where upstream published it. The generation loop's inner
  counter no longer publishes per token, because it is synchronous code inside
  an async execution; `tqdm` is also gone, as a guest has no console.

## Behavior notes

- `convert_to_safetensors` is retained in both loaders for workflow
  compatibility and is inert: every declared weight is already SafeTensors and
  the host parses it structurally before storing it, so the request is already
  satisfied whichever way it is set. Upstream's `torch.load` + re-save path,
  which read a pickle, is not reproduced.
- `keep_model_loaded` no longer keeps a model in a host-global cache, because
  the model is built inside the guest for the call. What it still buys is the
  host's warm weight cache, which `assets.load_state_dict` keeps regardless, so
  a second run does not re-read the weights from disk.
- `torch.manual_seed` is preserved verbatim. In a guest it is confined to this
  pack's own process, which is strictly narrower than upstream's host-global
  effect.
- The `NikshepShetty/Florence-2-pixelprose` adapter sets `use_rslora`. Upstream
  ignores it and applies `alpha / rank`; this conversion reproduces upstream,
  not peft.

## Undeclared upstream dependency

Upstream imports `torchvision.transforms.functional` and `PIL` without listing
either in `pyproject.toml`. Both are added to the v2 `dependencies` so the pack
can state what it actually needs; this is a reported upstream gap, not a
conversion workaround.

## Exercised boundary

The conversion suite runs all four node schemas and descriptors through a real
`GuestSession`, including successful declared model/LoRA acquisition and local
catalogue resolution, plus fail-closed checks for missing `models.download`,
`assets`, and `raw` authority and for a provider returning the wrong asset.
Pack-owned LoRA arithmetic, tokenizer hashing and parsing, state-dict-derived
configuration, model construction, weight loading through
`assets.load_state_dict`, attention/manual-cast operations, and an
autoregressive generation step are exercised hermetically with a reduced
Florence-2 configuration.

A released 463 MB+ Florence-2 checkpoint was not downloaded or fully inferred
during the hermetic suite. That is the remaining hardware/network boundary;
the exact production SafeTensors objects and their revisions/digests were
verified independently as described above.
