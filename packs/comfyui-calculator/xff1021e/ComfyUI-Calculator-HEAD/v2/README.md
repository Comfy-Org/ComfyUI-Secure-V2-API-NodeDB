# ComfyUI Calculator — Secure Nodes V2

Add **Calculator 🧮** to a workflow for a standalone four-function
calculator inside the node. It preserves the original digits, decimal point,
operators, clear button, result continuation, compact 15-character display,
and zero-input/zero-output backend node.

The interface is mounted with the typed Nodes V2 widget API. Calculator state
remains local to each mounted node, just as upstream; it is not added to the
workflow or prompt. Arithmetic is evaluated by a small deterministic parser
rather than JavaScript code evaluation.

The conversion uses no network, filesystem, storage, backend route, media,
clipboard, global keyboard, or ambient page-DOM authority.

## License

MIT — see [LICENSE](LICENSE).
