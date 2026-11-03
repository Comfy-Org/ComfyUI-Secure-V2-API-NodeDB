# Secure conversion report: ComfyUI-EasyCivitai-XTNodes

- Upstream: `https://github.com/X-T-E-R/ComfyUI-EasyCivitai-XTNodes`
- Pinned commit: `afba95227fb2ffad52cc5a0dc5ed6ef1fe98da68` (version 0.2.0)
- Status, round 1: **2 nodes converted**: `XTNodesPromptConcatenate` (Prompt Concatenate(XTNodes)) and
  `XTNodesCleanPrompt` (Clean Prompt(XTNodes)). They keep their original ids, display names, category and inputs.
- **The pack's other declared nodes are not registered in this round:** the Civitai URL loaders and the local loaders
  with previews. They download models from Civitai at run time and read model files and preview images from the
  host. Named refusal stubs may follow in a later round.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Only `io` schema types are used, and all of them are also in 0b86765f,
  so no minimum base applies.
- Frontend: not served (see known difference 1). Routes: none.

## How it runs
- `__init__.py` registers only `xt_prompt_nodes.py`. The original imported every module matched by
  `civitaiNodes/**/*.py` and appended the pack folder to `sys.path`.
- `xt_prompt_nodes.py` declares the two nodes as V3 schemas. Its `execute` methods call the original node methods in
  `civitaiNodes/prompt_concatenate.py`, which is unchanged, with the inputs exactly as provided. The returned result
  and UI text are the original's.
- Both nodes are pure value nodes: inputs arrive as plain values, and they use no host capability.
- `pyproject.toml` declares `requires-python = ">=3.13,<3.14"`. Its `dependencies` are empty: the converted nodes
  import none of the loaders' packages (blake3, sanitize_filename, pydantic, dynaconf, codetiming).
- The bundled Windows downloader executable (`aria2/aria2c.exe`) is not part of v2. Only the loaders use it.

## Parity (tier 1, CPU gate)
`tests/test_easycivitai_parity.py` runs the original nodes and the V2 nodes side by side and compares the returned
result, the UI text and raised exceptions (type and message) exactly. It covers:
- strings with commas, newlines, tabs, full-width commas, underscores, duplicates, punctuation and non-ASCII text;
- nested lists, numbers, booleans and None;
- every combination of `remove_duplicates` and `whitespace_style`, with any subset of the five prompt inputs
  connected;
- an unconnected `prompt` on Clean Prompt, which raises the original's TypeError.
The node interface is compared too. A perturbed result must turn the comparator red.

## Known differences
1. **The result text is not shown on the node.** The original's `web/js/civitai_xt_nodes.js` puts each prompt node's
   UI text into a read-only widget on the node, and adds preview widgets for the loaders. That extension is not
   served in this round. The nodes still return the same UI text and output value.
2. **Inputs cross the sandbox transport as JSON-like values.** A tuple arrives as a list, so it is joined like a list
   instead of being turned into text with `str()`. Dict keys arrive as strings. Live engine objects (MODEL, CLIP, VAE,
   ...) cannot reach these nodes. Very large UI text is limited by the transport's message size.
3. **Errors.** Errors raised during execution reach the host through the sandbox transport as
   `WireError("<Type>: <message>")`. The message text is preserved.
