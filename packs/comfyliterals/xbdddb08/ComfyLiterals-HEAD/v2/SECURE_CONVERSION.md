# Secure conversion report: ComfyLiterals

- Upstream: `https://github.com/M1kep/ComfyLiterals`
- Pinned commit: `bdddb08ca82d90d75d97b1d437a652e0284a32ac`
- Status: **converted 7 of 7 declared nodes** (`Int`, `Float`, `String`, `KepStringLiteral`, `Operation`, `Checkpoint`,
  `Lora`), 0 refused
- Frontend: not served (see known differences). Routes: none.
- SDK: target base 0cd9adec (comfy_api 0.37.0). Only `io` schema types are used, and all of them are also in
  0b86765f, so no minimum base applies.

## What changed (boundary only)

- `nodes.py` and `operations.py`: each node is a V3 `io.ComfyNode` with the original id, display name, category,
  inputs, outputs and output names. The value-handling lines are the original's:
  - `int(...)` / `float(...)` and their error messages;
  - the string passthrough;
  - the list-literal split;
  - the arithmetic and type selection in `Operation`, including its console print.
- `String` and `KepStringLiteral` were one class registered twice in the original; V2 declares two classes, because a
  V3 class carries its own id.
- `__init__.py`: the import-time `symlink_web_dir` call is removed. It created a symlink in the host's
  `web/extensions` folder, and a sandboxed pack does not write to the host.
- `pyproject.toml` is added to declare the Python version (`>=3.13,<3.14`). The pack has no dependencies.

## Parity (tier 1, CPU gate)

`tests/test_comfyliterals_parity.py` runs the original and v2 side by side and compares outputs exactly: the type, and
`float.hex` for floats. Raised exceptions are compared by type and message, and console output is compared too.
- Int and Float: 26 input strings each (signs, spaces, exponents, underscores, hex, non-ASCII digits, inf/nan, empty,
  invalid).
- String and KepStringLiteral: multiline, unicode and long strings.
- Checkpoint and Lora: blank lines and empty input.
- Operation: every type pair × every operation × int and float values (including zero, inf and nan), plus the error
  paths when the selected input isn't connected.
- The node interface, for every node.
A perturbed float result must turn the comparator red.

## Known differences

1. `Checkpoint` / `Lora`: the original pre-fills a NEW node's text box with the host's checkpoint or LoRA file names
   (`nodes.py:92`, `:120`). A V2 schema is static, so the default is empty. Saved workflows carry their own text and
   behave identically.
2. `Operation`: the original's frontend extension (`js/operation-node.js`), which hides the unused A/B input after a
   type change, is not served. The node shows all four optional inputs, and evaluation is unchanged.
3. Errors raised during execution (e.g. `Exception("Invalid value provided for INT")`, `ZeroDivisionError`, a missing
   input's `KeyError`) reach the host through the sandbox transport as `WireError("<Type>: <message>")`. The message
   text is preserved; the exception class is not. This applies to every Secure Nodes pack.
