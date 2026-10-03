# ComfyUI Nixie Timer — Secure Nodes V2

Add **NixieTimer** to a workflow to show a live world clock and a shared
inference timer inside the node. The timer starts when a queue attempt begins,
stops when the queue empties or execution fails, is interrupted, or is
rejected, and retains the completed elapsed time until the next run.

The seven original glow themes and ten translated labels are preserved. The
mounted panel follows node resizing and every visible instance shares the same
run clock, as in the upstream extension.

This conversion uses only typed V2 queue, settings, node, widget, and backend
event handles. It does not patch ComfyUI globals or access the ambient page
DOM, network, filesystem, storage, clipboard, or server routes.

## License

MIT — see [LICENSE](LICENSE).
