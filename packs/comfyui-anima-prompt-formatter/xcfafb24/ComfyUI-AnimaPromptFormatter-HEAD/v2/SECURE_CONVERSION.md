# Secure conversion report

- Upstream: `https://github.com/1lch2/ComfyUI-AnimaPromptFormatter`
- Pinned commit: `cfafb2498eccd7b860fe0ffecd382ec468a13aea`
- Python census: **1 supported, 0 rejected, 0 pending**
- Frontend census: **0 extensions, 0 JS-only nodes**
- Routes: **0**

`AnimaPromptFormatter` preserves its node and display IDs, category, multiline
input/default/display hint, named string output, and exact CR/LF, comma,
whitespace, and empty-tag normalization behavior.

The node has no permissions or host authority. A 1,048,576-character bound
fails closed before splitting an excessive direct input.
