# Placeholder Replacer By ID — Secure Sandbox V2

This conversion preserves the original node's 11 inputs, three string outputs,
placeholder replacement, toggle precedence, debug text and native errors.
It uses the unchanged parser from pinned Git commit
`57266363cbd939657ce89df5f7b4924657c97830` (project version 1.0.1).

Install the V2 distribution through a compatible Secure Sandbox pack registry.
The registry loads `secure-nodes.json`; the runtime requirement is Python 3.13
(`>=3.13,<3.14`). The node requires no model files, frontend extension, routes,
third-party packages, or additional SDK capabilities.

The input `id_sequences` is one custom `INT_LIST` value, not an execution list.
Outputs are `resolved_prompts`, `debug_info`, and `primary_ids`. For original
usage and examples, see the preserved README beside the pristine source.

The conversion was tested through the real registry TEST runner with gVisor:
14 exact three-string positive cases, three intended error cases, and a
post-error recovery. The TEST-only producer and observer are supplied with the
validation request; they are not production nodes. Prepared workflows under
`tests/` require that test harness. See `SECURE_CONVERSION.md` for evidence scope.

The original MIT license and copyright notice are retained in `LICENSE`.
