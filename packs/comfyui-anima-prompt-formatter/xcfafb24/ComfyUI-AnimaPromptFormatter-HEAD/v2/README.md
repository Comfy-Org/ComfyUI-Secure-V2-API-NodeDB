# ComfyUI-AnimaPromptFormatter — Secure Nodes V2

This conversion preserves the pack's prompt normalization: line breaks become
spaces, comma-separated tags are trimmed, empty tags are removed, and the
remaining tags are joined with one space after each comma.

The node is deterministic and runs without filesystem, network, model, raw,
storage, graph, backend, or frontend authority.
