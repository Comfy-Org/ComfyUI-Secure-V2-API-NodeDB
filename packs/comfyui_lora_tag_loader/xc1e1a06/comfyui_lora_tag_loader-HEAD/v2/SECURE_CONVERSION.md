# comfyui_lora_tag_loader: Secure Nodes V2 conversion

Upstream: https://github.com/badjeff/comfyui_lora_tag_loader at `c1e1a061d42384e06ff6c547c4a00aef7cc96e59` (key `xc1e1a06`).
UNRUN-IN-GUEST: the tier-1 parity below ran in the lane gate, not in a guest or a browser.

**Status:** converted 1 of 1 declared node (`LoraTagLoader`, display name "Load LoRA Tag", category `loaders`).
Nothing is refused. There are no frontend files, routes or weights.

## What changed (mirror mode; every hunk is a boundary change)
- `nodes.py`:
  - The class is an `io.ComfyNode` with the original id, display name, category, inputs and output names.
  - `execute` calls the original `load_lora` body, which is now `async`.
  - The tag regex literal (now a class attribute), the tag split, the strength parsing and its `ValueError` skip, the
    catalogue prefix match, both prints and the prompt cleanup are upstream's code, byte for byte (CRLF kept).
  - Only two host calls change:
    - `folder_paths.get_filename_list("loras")` → `await sdk.ctx().assets.list("loras")`;
    - `folder_paths.get_full_path` + `comfy.utils.load_torch_file` + `comfy.sd.load_lora_for_models` →
      `await sdk.ctx().assets.resolve("loras", name)` + `await model.apply_lora(asset, clip, wModel, wClip, skip_zero=False,
      allow_extended_strengths=True)`.
  - The two options keep upstream's behaviour: a zero strength still loads and clones, and a strength is never
    range-checked (upstream passes `float()` results such as `1e3`, `inf` and `nan` straight to Core).
  - The host op loads with `safe_load=True` and calls the same `comfy.sd.load_lora_for_models`.
  - `SDK_REFS = True`; `SDK_PERMISSIONS = ("assets",)`.
- `__init__.py` also exports `comfy_entrypoint`.
- New files: `pyproject.toml` (Python `>=3.13,<3.14`); `secure-nodes.json` from the real encoder; `comfy-api.pyi` and
  `comfy-api.d.ts` copied byte-for-byte from the published pack stubs; this file; `tests/`.

## Parity (tier 1, gate)
`tests/test_comfyui_lora_tag_loader_parity.py`: 4,092 texts (92 hand-picked plus 4,000 seeded fuzz), including
malformed, unclosed, nested, unicode, newline-in-tag and out-of-range tags. Compared byte for byte or exactly:
- the STRING output;
- every LoRA application in order (catalogue name, `safe_load`, both strengths as `float.hex`, and which model/clip it
  applied to);
- whether MODEL/CLIP are the inputs or the last application;
- the printed lines;
- any exception.

Result: EXACT, 0 mismatches, 509 applications.
- The schema matches `INPUT_TYPES`/`RETURN_*`.
- `secure-nodes.json` equals the real encoder's output.
- A negative control (one perturbed output) turns red.
- Counterfactual: with the op's default options, 308 of the 4,092 cases would differ.

Core's LoRA math runs on the host in both versions (`comfy.sd.load_lora_for_models`). Checking it on a real model is
tier 2.

## SDK use (minimum base 0cd9adec)
- `sdk.ctx().assets.list` and `.resolve` are public.
- `ModelRef.apply_lora` and its `skip_zero` keyword are in the published `comfy-api.pyi`.
- `allow_extended_strengths` exists in the comfy_api 0.37.0 runtime (`_sdk.py`) and the host transport, but not in a
  public stub. API ask: publish it, and publish `apply_lora` in `_sdk_public.pyi`.

## Known differences
- The host op also passes the LoRA file's safetensors metadata to `load_lora_for_models` (`lora_metadata`), which
  attaches it to the patched model and clip. Upstream passes none. This is not expected to change sampling;
  unverified, tier 2.
- No LoRA state dict is cached between runs (upstream kept the last one per node instance). Speed only.
- `assets.list` normalises `\` to `/`. Catalogue names, and the prefix match on them, differ only on a Windows host.
- Upstream's regex literal raises Python's invalid-escape `SyntaxWarning` at import. The line is kept as upstream's.
