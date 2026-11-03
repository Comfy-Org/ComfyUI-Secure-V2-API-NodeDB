# Secure conversion notes

Pinned upstream commit: `44de705818d4663fefefde57ffe0ea5a9ea39df4` (ltdrdata/was-node-suite-comfyui). The sealed node
schemas and permissions are in `secure-nodes.json`.

Status: 35 of the 220 registered node ids are converted. The other 185 are registered with their real schemas and refuse
with `was-ns/<node id> is not yet converted to Secure Nodes V2`: at validation, or, for Number PI (it has no inputs,
so core never calls its validate_inputs), when it runs. The original declares one more id,
`CLIPTextEncode (BlenderNeko Advanced + NSP)`, only when another pack (ComfyUI_ADV_CLIP_emb) is installed
(WAS_Node_Suite.py:14662-14720). It is not registered here.

Converted:
- Round 1: Text to String, Text to Number, String to Text, Number to Int, Text Concatenate, Text Find and Replace, Text
  Multiline, Text to Conditioning, Load Lora, Lora Loader, Image Filter Adjustments, Latent Noise Injection and Image
  Save.
- Round 2: Seed, Constant Number, Number Operation, Number to String, Number to Float, Number to Text, Logic Boolean,
  the Latent, Lora, VAE, Text, Model and Conditioning Input Switches, Text List, Text List to Text, Text List
  Concatenate, Text String, Text Multiline (Code Compatible), Text Parse Tokens, Text Compare, Text String Truncate and
  Text Random Line.

## How the conversion is built

- V2 never imports `WAS_Node_Suite.py`. On import the original writes configuration and history files into its pack
  folder, can run pip, and imports host modules. The file stays in this folder byte for byte, as data.
- Every id is registered from `was_v2/schemas.json`: the original's own INPUT_TYPES(), RETURN_TYPES, RETURN_NAMES,
  OUTPUT_NODE, CATEGORY and list flags, captured from the pinned code with its default configuration. Each id has its
  own class (`was_v2/nodes.py`).
- The value and pixel nodes run the original's classes, copied verbatim into `was_v2/originals.py`. The build checks
  each block byte for byte; the source lines are noted above each block.
- Models, conditioning and files go through the guest SDK:
  - Text to Conditioning: `clip.tokenize` / `encode_from_tokens_scheduled`, as core's CLIPTextEncode.
  - Load Lora / Lora Loader: `ModelRef.apply_lora` with a LoRA from the host catalogue.
  - Image Save: the managed image writer, inside the output folder.
- Model menus (Load Lora, Lora Loader, the three checkpoint loaders, Upscale Model Loader): the original listed a model
  folder when its INPUT_TYPES ran. V2 declares the host's catalogue route for the same folder, and the host fills the
  menu.

## Parity

`tests/test_was_node_suite_parity.py` runs the pristine pack and this conversion through ComfyUI's real executor, side
by side, on generated test workflows:
- weightless MODEL/CLIP stand-ins that record every LoRA patch;
- frozen clocks, and the global torch RNG seeded before every prompt.
It checks every converted node's outputs and files, the error and refusal cases, one refused node, and the schema of
every registered id against the original. A tampered output must turn the comparison red.

## Known differences

- Image Save:
  - Refused by name:
    - extension jpg/jpeg: the writer's JPEG subsampling differs from Pillow's default;
    - webp with embed_workflow: the original writes the prompt and workflow into EXIF 0x010F/0x010E
      (WAS_Node_Suite.py:7459-7463);
    - show_history: the original reads its history database from its pack folder;
    - output paths outside the output folder (absolute, Windows or `..`), and path separators in filename_prefix;
    - replacing an existing file: the managed writer never overwrites;
    - an output folder with more names than the asset catalogue lists at once (4096).
  - PNG files lack the pHYs (DPI) chunk the original writes (`dpi=(dpi, dpi)`, WAS_Node_Suite.py:7490-7497). WEBP files
    lack the original's empty EXIF chunk. Pixels and text chunks are identical.
- Text Multiline and Image Save tokens:
  - `[time]` and `[time(...)]` use the guest's clock.
  - `[hostname]`, `[user]`, `[cuda_device]` and `[cuda_name]` read the host machine (WAS_Node_Suite.py:878-896) and are
    refused by name.
  - There is no settings database, so there are no custom tokens (the original's default).
- Load Lora / Lora Loader: the host's LoRA loader also attaches the LoRA file's metadata to the patched model and
  clip. The original's patches are otherwise identical.
- Latent Noise Injection draws its noise from the process's global torch RNG (WAS_Node_Suite.py:8910), as the
  original does. The guest's RNG is not the host's: outputs are equal only when both start from the same RNG state.
  In a live graph the original's state depends on what ran before it (for example a sampler's seeding).
- Text Random Line seeds Python's `random` module and draws a line, as the original does (WAS_Node_Suite.py:10499-10503).
  The line is the same, but the reseeded module is the guest's: a later node of another pack that draws from the
  host's `random` no longer sees that seed.
- Text Compare in similarity mode collects the similar words in a Python set (WAS_Node_Suite.py:10476). With more
  than one word, their order follows the process's string-hash seed, so it differs between runs of the original too.
- Text Parse Tokens re-runs on every prompt, as the original (its IS_CHANGED returns NaN).
- The engine-object switches (Latent, Lora, VAE, Model and Conditioning Input Switch) take handles and return the
  chosen one unchanged, as the original returned the chosen object.
- Schemas of refused nodes come from the default configuration:
  - the style menus (no styles.json) and the history loaders (no history database);
  - Diffusers Model Loader (no diffusers folders) and Cache Node's suffix defaults (the original draws random digits on
    every call);
  - the absolute-path defaults of Cache Node and Write to GIF, which are blank here.
