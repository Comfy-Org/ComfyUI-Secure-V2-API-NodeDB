# Amendments to I2V_STEP1_DESIGN_r1.md (r2)

- **Line 79, H2 "variant by the admitted record":** H2 picks the variant by the original's name rules
  (`nodes_model_loading.py:1374-1392`), including "high"/"low". The admission record fixes the model type and the patch shape.
  This is deliberate original parity; see DELTA_NOTES_r2.md L2.
- **Lines 71-73, H1 required values:** H1 admits exactly the 13-key set from `WanVideoImageToVideoEncode`. It requires None for
  `negative_clip_context`, `end_image`, `add_cond_latents` and `control_embeds`, and `has_ref` False. It does not check the types
  of `image_embeds`, `mask` or `clip_context`; malformed values fail inside the original code. The type refusals (review L3) are
  deferred to the next production revision.
- **Line 105, image:** the bound run uses image e48accf7 (accelerate 1.10.1, gguf 0.17.1, from the r2 locks), as feta r3 did. It
  does not use 862ab95d with the Qwen deps.
- **Cases:** t1 is added (review M2): the plain I2V dict with the approved T2V model on the published admission. The original
  `ValueError` is raised after load, and parity is checked.
