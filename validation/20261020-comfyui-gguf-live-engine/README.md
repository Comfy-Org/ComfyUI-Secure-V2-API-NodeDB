comfyui-gguf docs-only note (2026-10-20): every node fails on the live service.

Source reading plus a read-only filesystem check of the live service (MERVYN, 2026-10-20). Nothing was run, and no code, manifest or test changed. Both host verbs this pack uses (`models.load_gguf_model`, `models.load_gguf_text_encoders`) first resolve the fixed ComfyUI-GGUF vendor module installed natively under `custom_nodes`; the text-encoder verb needs it even for ordinary state dictionaries. The live service has no ComfyUI-GGUF custom node and no `gguf` package, so all 6 nodes fail when run.

Files:
- `GGUF_LIVE_FACTS.json`: the live check, and line references with file hashes in the deployed engine SDK, this pack's `v2/nodes.py` and the pristine upstream `loader.py`.
