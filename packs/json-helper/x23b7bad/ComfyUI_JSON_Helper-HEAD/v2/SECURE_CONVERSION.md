# JSON Helper — exact Git V2 source conversion

The selected Git baseline is `23b7bad7c112dfad9140d5754ba1f6ef50ee720a`, from
https://github.com/a-und-b/ComfyUI_JSON_Helper. The pristine sibling retains all
eight tracked blobs, their Git modes, project version 1.0.0, and `node.zip`.
The separate Registry 1.0.1 archive has different project metadata and omits
`node.zip`; it is not claimed to be byte-identical to this Git snapshot.

The original `JSONStringToObjectNode` identity, display name, multiline STRING
input and custom JSON output are preserved. The parser module is byte-identical
to the pinned source. The V2 entry wraps its native result in `io.NodeOutput`.
Invalid JSON retains its native printed message and `None` result; other native
exceptions propagate. The wrapper adds no root, depth, length, or finite-value
limits. The service's transport rules remain separate from parser behavior.

This pack has one backend node, no frontend extension or routes, and no model,
network, persistence or private dependency requirements. It declares zero
capabilities and `SDK_REFS=True`. Python `>=3.13,<3.14` is declared in both
`pyproject.toml` and the canonical manifest, with resolved minor version 3.13.
API declarations and the manifest were generated from the installed SDK.

Validation completed on 2026-10-13:

- 22 distinct registered runtime cases cover JSON roots and edge values, with
  an expected-failure control.
- Final canonical declarations passed ten edge cases in required gVisor job
  `ef098215f5725a3fc3d13e667318d52c`; the test session was then released.
- The patch pair reconstructs the complete V2 tree with identical bytes and
  modes while preserving all pristine source files.
- Manager review confirmed the unchanged parser, native node contract and
  recorded guest behavior.

Historical TEST requests preserve the exact documentation they contained when
submitted. Their earlier pending text is superseded by this completion record.
This documentation update changes no production Python, manifest or declaration
bytes. See the corpus validation evidence for the resulting distribution hashes.
These checks do not imply deployment to the live registry.
