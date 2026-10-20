# String List Concat — Secure Nodes V2 (1 of 1 node)

Upstream: <https://github.com/tttamaki/ComfyUI-StringListConcat>, pinned
commit `8237a610ca361268ccea68442c2986b20248a33a`, release `x8237a61`. The 4
tracked original files are preserved byte for byte.

## Node scope

| Node | Status | Finite purposes (cases; original errors) |
| --- | --- | --- |
| `StringListConcat` | tested: original vs default SDK, and Core-finalized original vs one required-Seatbelt Guest | Native: 19 cases (13 graph-shaped, 2 execute-only, 4 original errors) with 5 wrong-data controls. Guest: 8 cases, including Autogrow order, the maximum 32 slots, Unicode, CRLF, sparse slots and one remote `TypeError` |

The upstream package registers one node, and this conversion registers the same one.

## Conversion notes

- The node is already a public V3 `ComfyNode`/`ComfyExtension`. These v2 files
  are byte-identical to the original:
  - `v2/nodes/string_list_concat.py`
  - `LICENSE`
  - `README.md`
- `v2/__init__.py` adds only
  `NODE_CLASS_MAPPINGS = {"StringListConcat": StringListConcat}`, the same
  single registration that `comfy_entrypoint()` returns.
- `v2/pyproject.toml` declares only `requires-python = ">=3.13,<3.14"`, to meet
  the single-minor runtime rule. It invents no name, version or publisher.
- The node has no dependencies, permissions (`SDK_PERMISSIONS` is empty),
  refs (`SDK_REFS` is false), routes, web directory, model weights or
  validation methods. No input-size caps were added; the original has none
  beyond Autogrow's 32 slots.

## Autogrow order (documented, unchanged)

The node joins `inputs.values()` with the delimiter, in the order of the dict it receives.

- **Called directly**, that is dict insertion order. The native cases
  `insertion-order-swapped` and `insertion-order-lexicographic` record this.
  For example, inputs `string1="B", string0="A"` return `B+A`.
- **Through Core**, Core builds the Autogrow dict from the template's dynamic
  paths in numeric slot order (`string0`, `string1`, …, `string31`), whatever
  the prompt key order. The original and the Guest receive and return exactly
  that order:
  - the same swapped prompt returns `A+B`;
  - a 12-key prompt in lexicographic order joins `string0` … `string11` numerically.
- Execute-only cases bypass Core's `min=2` validation and are labelled as such.

## Actual evidence and limitations

One selected combined attempt, `m_cf26ea3fe5`, ran on MIKE's existing shared
owner (task row `stringlist_combined`, the startup path of the passing Join R6
Guest job). The environment:
- Python 3.13.14;
- Core `44564d0279c275eef52b11750a9d76349f4e7a88`;
- backend `59bd3e1acba6520bb32717ad03833f6ab2967ecc`;
- profile `40fbb95d729e2f10ba9c7809fa08135f5d9f433372d41d2d9d044cd58a68cdaf`.

The run:
- There was one trusted host process with serial stages: environment check,
  genuine generator, native comparison, Guest boundary, canonical pair/bundle
  and both pristine replays. Exit status was 0, with no automatic retry.
- Owner wall time was **41.3 s**. The owner's sampled
  aggregate RSS peak (0.1 s polling) was **808,648,704 bytes**.
- `/usr/bin/time -l` around the owner reported a maximum resident set of
  **1,068,630,016 bytes** for the largest process in the tree. The true
  peak therefore came within a few MB of the sampled 1 GiB watchdog, which is
  an observation and not a quota. The polled aggregate understated the peak.
- stderr held only environment warnings from the shared venv: torch's `pynvml`
  deprecation notice, and duplicate `libavdevice` Objective-C classes bundled by
  `av` and `cv2`. No warning was recorded during any node execution.
- Native: the full original was registered through its own `comfy_entrypoint`
  and compared with the converted class through actual default-SDK dispatch.
  Each of the 19 cases compared typed values (UTF-8 bytes and hashes), console,
  warnings and unmutated inputs exactly. The schema projection matched, and all
  5 wrong-data controls were detected.
- Guest: 8 cases compared the Core-finalized original with the generated packdb
  proxy, dispatched to one genuine required-Seatbelt Guest:
  - each outcome matched its bound expectation;
  - the key order sent to the Guest equalled the order the original receives;
  - the remote error type and message matched;
  - a corrupted-output control was detected;
  - the Guest was retired, with its process group and socket directory absent.

  The native stage ran inside the owner-supervised trusted host, like Join R6's
  Core reference. It did not run under a per-worker deny-network profile.

Evidence and reviews:
- The evidence archive is 12,980,923 bytes, SHA-256
  `7ddd34e14385748161ebb4045d7d2e92d945520e544cd8deaafac08d5f8d3681`.
- The independent data-only intake made 46 checks and recomputed every
  outcome from the frozen cases without importing SDK, Core or pack code. Its
  receipt is `dbd0c291dc7c607873b1263c7c3c5d8c1f769d90241bbf54468845b1e5ec14a7`.
- Compact records are in `validation/20261020-stringlistconcat-combined-r2`. Raw archives stay
  outside Git.

## Generation

The normal generated manifest is retained byte for byte:
`3f1717b90cf6b8f69d46256e9ef7a3c36964daf03c05bc6a1e312c57e08c8e93`. The official generator produced it inside the same
attempt, using the accepted tool plus one profile line.

After the attempt, only non-runtime files were added:
- this report;
- the API declaration contracts `comfy-api.pyi` (`42b9ec2d…`) and
  `comfy-api.d.ts` (`abf1417d…`). These are the genuine current output of
  `comfy_secure_nodes.apistubs.generate` (authoring result `e65b26f5…`), whose
  141 SDK files exactly equal the qualified f1 profile this attempt used. They
  are copied byte for byte from the published Light Tool/Studio contract
  (independent reuse review `c1d33070…`); no stub generator was run for this pack.

Canonical pair and bundle regeneration, plus both pristine file-only replays,
preserve all original and converted files and Unix modes.

**Not claimed:** runtime or dependency-profile admission, registry adoption, a public
graph executor or queue, the browser Autogrow slot UI, managed/gVisor Guests and
deployed-service acceptance.
