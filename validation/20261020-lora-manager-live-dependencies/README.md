LoRA Manager rev 7 (docs only): live dependency status.

Source reading plus a read-only filesystem check of the live service (MERVYN, 2026-10-20). Nothing was run, and no code, manifest or test changed. Load Image Metadata imports `piexif` on every run (`v2/secure_services/image_metadata_source.py`, `fields_from_bytes`, reached from the node's `execute` for every image). The pack declares no dependency profile, and the live service has no `piexif`, so every run of that node fails there after validation passes. No other registered node imports a third-party package beyond core-provided `torch`, `numpy`, `PIL` and `av`. Counts are unchanged.

Files:
- `IMPORT_CENSUS.json`: every third-party import reachable from `v2/__init__.py` (76 modules), with line and lazy/module level.
- `LIVE_DEPENDENCY_FACTS.json`: the live check, the manifest's runtime keys, and line references with file hashes for the piexif path, the original's requirement, and the SDK GGUF verb's dependency on a host-installed ComfyUI-GGUF.
