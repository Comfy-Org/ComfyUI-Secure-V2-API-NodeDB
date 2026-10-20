# Marko Text â€” Secure Nodes V2

This source conversion is pinned to
`MarkoCa1/ComfyUI-Text@e66277dd0acf2c0f3bfce949600a3177f513b056`.
All twelve tracked original files remain byte-exact. The converted mirror
retains the four original node IDs, display names, categories, input order,
defaults, output names and output-node flag. No publisher, license or upstream
version is invented.

The selected development-profile comparison passed 100 native cases paired
with 100 actual required-Seatbelt Guest dispatches. Each ordinary case must
return the same typed one-string tuple and custom UI value. Matching exceptions
do not count as successful ordinary results.

| Original node ID | Finite ordinary cases | Preserved purpose |
| --- | ---: | --- |
| `ShowText` | 12 | Return the input string unchanged and publish the exact custom UI object `{"string": [text]}`. |
| `CombinationText` | 32 | Join the two strings using the connector verbatim, preserving empty strings, Unicode and whitespace. |
| `PlaceholderText` | 24 | Apply the original ordered placeholder replacements, including replacement cascades. |
| `ReplaceText` | 32 | Split the old-string field on commas and replace each part in order, including empty parts and replacement cascades. |

## Boundary and computation

The original computation classes in `MKTextNode.py` are textually extracted
into `_algorithms.py`, with unchanged class text and AST. The V2 classes in
`nodes.py` are real module globals derived from the public `io.ComfyNode` API.
All four declare `SDK_REFS=True` and request no capabilities. Strings cross the
ordinary wire as values. `ShowText` uses `io.NodeOutput.from_dict` to preserve
its original `ui.string` value; the other nodes return `io.NodeOutput` with the
unchanged original result tuple.

The V2 initializer imports only the node mappings. It does not invoke the
legacy installer, run pip, modify `sys.path`, or copy frontend files into a
host extension directory. The pristine original initializer and installer are
retained as the canonical diff base. The original requirements file is empty.
No model weights, model forwards or network acquisition are required by these
four purposes.

The frontend source uses public `comfy.defs` and widget APIs. It preserves the
ordered trim/filter/join behavior for the display and limits its `ShowText`
extension to category `MK/text`. Its stable internal readout name replaces the
legacy graph-count-derived name. Browser rendering, workflow serialization,
API-prompt exclusion, renderer behavior and subgraph behavior have not been
executed or qualified by the backend comparison.

## Retained execution evidence

The actual scientific attempt used the trusted normal-site Host and one
required genuine Seatbelt Guest, with source-bound public SDK
`f1a73e4f160e70862f51abdddbb9268e2ce94dd96e18455a79e42307a443f91c`.
It completed four ordered schema comparisons and five comparator controls:
wrong output arity, wrong custom UI, changed scalar type, ordinary result
versus error, and paired matching errors. The controls must be rejected.

The actual normal generator produced the four-node `secure-nodes.json`, which
is retained byte-exact. The scientific attempt generated the canonical pair
and bundle, applied both to independent pristine copies, and refused two
deliberately changed `__init__.py` bases with specific canonical base-mismatch
errors. Both raw before and after inventories were retained for each refusal.
The unchanged-inventory checks establish that those failed applications did
not mutate the changed-base fixtures.

Five full source/runtime/operator map groups were unchanged. Independent
retirement evidence records seven PIDs and four actual process groups absent
twice. This is evidence for the selected normal execution and observed
processes. It does not qualify every short-lived descendant, cancellation or
uncatchable parent-failure path. The selected 2 GiB memory bound is sampled RSS,
not a hard memory quota.

The owned temporary root remained with only an empty mode-0755 `home`
directory; complete temporary-root removal is not claimed. INPUT map raw JSON
hashes differ because of dictionary key ordering, while all 51 complete
path/hash/byte-count/numeric-mode rows remain equal. Host import origins were
measured; no separate Guest-module hash telemetry is claimed. The actual
required Guest command, saved sandbox profile, live PID identity and 100
returned observations bind this finite execution. The passive observer's own
PID/PGID is recorded without a separate full live UID/start identity.

The execution archive is 17,504,131 bytes, SHA-256
`1fa43ddff06e48ed7edf2062f8f4222852519437bfd01198aeaea02a11fbeec3`,
with 208 members and 207 pinned payload files. Root's independent strict-data
verification and compact source-publication receipts accompany this source.
Raw execution archives and runtime inventories remain outside the Git ingest.

## Public contracts and distribution

The tested candidate already contains the genuine public contract files:

- `comfy-api.pyi`: `42b9ec2d9f7db0190c39fe5207c4253aaf04ec7851a52cb59c6e667a538478a7`.
- `comfy-api.d.ts`: `abf1417d3d2fa5edf993fbf1965c3df4386ea27bf357264bc0588fa5bb5099d2`.

Their existing generated lineage and equivalence to the same f1 SDK sources
were approved for reuse. The files are retained exactly. No handwritten
declarations or new contract generation are introduced during publication.

Only this report changes after the scientific attempt. File-only canonical
pair/bundle regeneration and two further independent pristine replays cover
the final source and its byte/mode inventory. These operations import no pack,
SDK or scientific module and do not rerun the normal manifest generator. The
canonical JSON/diff pair is included in the ingest; the derived bundle ZIP is
kept outside it.

This qualifies the finite backend purposes above in the tested development
profile. It does not establish managed dependency-profile admission, deployed
service behavior, public queue execution, frontend acceptance or registry
adoption. `ShowText` attribution is limited to this exact stamped upstream
revision. The four historical stamped workflows did not survive the retained
content-erasure screen, so no current corpus-unlock claim follows.
