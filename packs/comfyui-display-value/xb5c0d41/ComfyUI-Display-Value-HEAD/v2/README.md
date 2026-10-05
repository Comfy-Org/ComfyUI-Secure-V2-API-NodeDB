# ComfyUI Display Value — Secure Nodes V2

This conversion preserves the value-formatting output node and replaces its
legacy prototype monkey-patching with an isolated mounted read-only display.
The displayed value is serialized as per-node, non-prompt workflow state and
updates after each execution.
