<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-apqnodes

## Provenance

- Upstream: https://github.com/AIPOQUE/ComfyUI-APQNodes
- Exact Git commit: `25a7aea3379259f9189a21e56a0160b6f8f8d02c`, release `x25a7aea`.
- All eight retained pristine paths and Git blob IDs matched the immutable Git tree, not live HEAD. Per-file SHA-256 and Git blob evidence: `source-provenance.json`.
- Candidate source: retained historical corpus; recorded downloads are zero/unavailable. No current trending, ranking or adoption claim.
- Snapshot is complete, including dotfiles, README, MIT license and node resources. No weights or runtime downloads.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `ColorPalette\|AIPOQUE` | supported | yes | supported within stated bounds; coordinator review required | Exact source algorithm AST, differential text/RGBA values, native errors, actual confined guest and production outer executor; see unique focused test below. |

Census: one Python node; zero rejected or pending implementations. This is a bounded conversion declaration, not user verification or a central count promotion.

## Frontend and ancillary scope

No frontend entrypoints, extension registrations, JS-only nodes, routes, model loaders, external services or side effects exist in the complete pinned source tree. No bridge is used.

## Behavior and authority

Original color table, nearest-color selection/tie order, text punctuation, newline handling, RGBA canvas, channel order and float32 normalization stay pack-side. The complete `color_picker` AST is unchanged. Three-digit hex is the source's grouped numeric interpretation, not CSS expansion. Empty strings and `#` preserve the zero-width `(1,64,0,4)` IMAGE tensor.

IDs, display/category, ordered STRING/IMAGE outputs, both forced-input STRING sockets, defaults and multiline flags are exact. Legacy dispatch is replaced with async V2 `execute`. The public `TensorRef.from_value` publisher is raw-permissioned in the genuine guest; no private constructors, host objects, paths, network, installation or process authority are requested. Trusted in-process execution is not a permission boundary; denial evidence comes from the actual guest broker.

Admission precedes source parsing/Pillow allocation: each string is at most 65,536 UTF-8 bytes and at most 256 nonempty source `#` segments. Maximum final canvas is `(1,64,16384,4)` float32, 16 MiB. This bounds the tested workload, not the host's aggregate memory or every allocator temporary. Non-string direct values and larger workloads deliberately fail closed.

## Source defects retained

The declared `hexcodes` default `World` raises native `ValueError`. Both sockets are force-input; valid connected hex values are usable. The conversion does not silently repair the default, claim default usability, expand CSS shorthand, or suppress malformed/whitespace-only source errors. Native invalid-hex exception types and actual guest messages are tested separately from workload refusal.

## Verification results

Unique test: `tests/test_ned_apq_conversion.py`. It covers exact loader/schema/manifest, original algorithm AST, text and pixel-exact controls, 200 seeded random valid comparisons, malformed source outcomes, maximum admitted canvas and UTF-8/direct-input limits, two fresh required confined guest processes with copied pack files, actual outer STRING/IMAGE outputs, raw denial and recovery, source/resource/license identity, frozen declarations and two exact patch/ZIP reconstructions with pre-write wrong-source refusal.

Run from `v2/tests`, with explicit canonical core and disabled bytecode:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_apq_conversion.py -q
```

Observed focused checkpoint: 53 passed, 1 artifact test deselected; the distinct external final handoff records the final unchanged-byte repeated complete results and hashes. Initial collection/fixture failures are retained in `outputs/ned-oct7-apq-focused-*.log`; they are not converted into passing claims. No mocked model or inference path exists in this pack.

## Release integrity and dependencies

- `secure-nodes.json` binds Python `>=3.13,<3.14` / resolved 3.13 and raw authority.
- Frozen Python composite: `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`, tested font-catalogue successor origin; that API is unused here.
- Frozen frontend composite: `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`, checked model-catalogue origin; frontend is absent.
- Managed installed Torch, NumPy and Pillow were used, no install or weight acquisition. The handoff records observed package versions. Dependency declarations alone are not sealed cloud provisioning proof.
- Pair reconstruction proves final V2 bytes; separate Git-blob correspondence proves pristine identity.

## Persistence and limitations

No durable state exists: all output derives from inputs and immutable source color data. Two fresh reconstructed pack filesystems/users/processes produce exact outputs; no cloud backing-store claim is needed or made. No file/global RNG/cache mutation is introduced.

Evidence is actual CPU tensors and macOS required sandbox guests plus the production outer executor, not Linux/cloud deployment, browser visualization, GPU, authenticated multitenant provisioning or complete downstream workflows. Downstream consumers of the source's empty-width IMAGE may reject it; the node's native output is preserved. Central integration, release review and user verification remain coordinator-owned.
