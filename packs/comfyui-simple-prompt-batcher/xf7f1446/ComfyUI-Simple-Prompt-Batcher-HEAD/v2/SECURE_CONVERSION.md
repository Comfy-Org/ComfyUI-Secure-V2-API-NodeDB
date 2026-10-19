# Simple Prompt Batcher — Secure Nodes V2

Pinned upstream: `f7f14462ff06a50cac6c14b668b822f6e2640a54`.

## Census and qualification scope

One original Python node and one converted registration. No frontend extensions
or backend routes. `SimplePromptBatcher` is tested for the native, full original
package versus the actual registered node using the default in-process SDK on
the selected Mac profile. This is not Guest, browser, deployed-service, or full
public graph qualification.

| Node | Status | Evidence and limits |
| --- | --- | --- |
| `SimplePromptBatcher` | tested (native original/default SDK basic behavior) | 25 exact input/result/console comparisons; real extension and input/output metadata checked. Public executor/downstream list flattening is a separate unexecuted gate. |

## Behavior

The node splits on literal newlines, strips and discards blank prompt lines,
preserves duplicates and order, and uses raw affix truthiness for comma insertion.
Empty or all-blank prompts return a list containing one empty string, even when
affixes are present. Output remains a one-element tuple containing a list of
strings, with the list output declaration preserved. Console previews retain
the original 60-codepoint cutoff and Unicode bytes.

Input order, defaults, multiline flags, placeholders, tooltips, output name,
category, display name and list flags are compared exactly. The historical
converted description adds informational class documentation; the original
legacy `DESCRIPTION` is empty. Exact legacy UI description parity is not claimed.

## Resource policy

The conversion retains its explicit narrowings: each input must be a string of
at most 4 MiB in UTF-8, at most 4096 nonempty prompts are allowed, and the expanded
UTF-8 output total must not exceed 16 MiB. These candidate type/size/count errors
are not described as original parity; the original is unbounded.

The output byte total is checked before constructing the expanded list. It is
the sum of the stripped prompt UTF-8 byte lengths plus the prompt count times
the raw affix byte lengths and any two-byte comma-space separators. Existing
empty-input and prompt-count checks retain their order, as does the existing
`ValueError("batched prompt output is too large")` for output overflow.

The one additional candidate-only resource control uses a 4 MiB UTF-8 affix and
4096 prompts, representing 17,179,881,472 expanded bytes. The original never
receives that control. An observer of the real helper's source lines verifies
that the prospective guard is reached and expansion is not; it stops the call
before expansion if that guard fails. It does not replace production objects.

## Evidence

- Actual environment: Python 3.13.14, `comfy_api` 0.42.0, Core
  `44564d0279c275eef52b11750a9d76349f4e7a88`, backend
  `59bd3e1acba6520bb32717ad03833f6ab2967ecc`.
- 25 genuine original-versus-default-SDK parity cases, 14 separately scoped
  candidate guard controls, one allocation preflight control, and six coherent
  corrupted-data controls detected by the comparator.
- 97 primary checks passed. Result archive SHA-256: `65a903417263e199e35bc7dede4b53b30a20df4321757b9feac1c487036107af`.
  Independent review SHA-256: `a680fe91448b74fb2b400e461107608510c4d16743b4a3dfc0b17f9c800df39e`.
- One selected native attempt under `m_33da65cd8e`; 3.5386687499999994 seconds,
  296648704 observed peak RSS bytes, no automatic retry. All eight worker
  groups and the outer owner group were independently absent; 16 worker cleanup
  rows confirmed leaders reaped and groups absent.
- The original eight Git blobs and file modes were preserved. Only `v2/nodes.py`
  changed in production: the exact prospective output guard precedes allocation.
  No SDK change, new resource cap, model, service, route, or network activity.
- The genuine normal generator produced the one-node manifest. Official pair
  and bundle generation and both pristine replays matched complete source bytes
  and Unix modes. This final source-only publication stage changes only this
  report after generation, retains that manifest byte for byte, and performs
  its own canonical file-only pair and bundle replays.

`SDK_REFS` is false and declared permissions are empty. Qualification of public
`PromptExecutor` mapping, downstream `OUTPUT_IS_LIST` flattening, multi-input
broadcasting, Guest execution, browser UI and deployed registry/service adoption
remains separate. No current acceptance claim is inferred from the older
supported label or workflow-ranking records.
