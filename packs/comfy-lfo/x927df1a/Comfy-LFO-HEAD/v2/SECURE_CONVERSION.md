<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfy-lfo

## Provenance

Upstream https://github.com/richinsley/Comfy-LFO, exact Git commit `927df1affa338e352286b3451c58acc1dd88541d`, release `x927df1a`. Every path/blob in the complete four-file retained snapshot matched the immutable Git tree; original file SHA-256 and actual loader census are recorded in `source-provenance.json`. No live source substitution. Retained corpus download field is zero/unavailable; no current popularity/trending assertion. Original MIT license is retained.

## Backend node dispositions

| Exact backend node ID | Disposition | Registered in V2 | Review recommendation | Evidence basis |
| --- | --- | --- | --- | --- |
| `LFO_Triangle` | supported | yes | bounded scalar behavior; coordinator review | Exact original source math, negative-phase quirk, seeded controls, actual confined guest/outer. |
| `LFO_Sine` | supported | yes | bounded scalar behavior; coordinator review | Exact original source math, phase/large input/native arithmetic-error controls, actual confined guest/outer. |
| `LFO_Sawtooth` | supported | yes | bounded scalar behavior; coordinator review | Exact original source math including truncation rather than modulo, actual confined guest/outer. |
| `LFO_Square` | supported | yes | bounded scalar behavior; coordinator review | Exact original threshold/phase/order and seeded controls, actual confined guest/outer. |
| `LFO_Pulse` | supported | yes | bounded scalar behavior; coordinator review | Exact original pulse-width/default/threshold and seeded controls, actual confined guest/outer. |

Five registered Python nodes; zero rejected or pending implementations. Declarations are not central integration, user verification or a count increment.

## Frontend and ancillary scope

The complete pinned pack has no frontend files/extensions, JS-only nodes, routes, model/weight dependencies or side effects. No legacy bridge.

## Behavior and authority

The entire original `lfonodes.py` remains byte-for-byte unchanged. New value-mode `io.ComfyNode` wrappers retain each exact ID, input ordering/default/step, category and one FLOAT output. All five algorithms remain pack-side. Zero permissions, `SDK_REFS=False`; only Python standard-library math and public `io` are used, with no host/model/raw/filesystem/network/process/object authority.

The source truncates `position*frequency` with `int`, not floor/modulo. Negative phases may produce triangle2.0/sawtooth-1.5 outside a conventional unit amplitude. These quirks, negative frequency/amplitude, offsets, pulse thresholds, large finite scalars and ordinary IEEE-double bits are retained, not normalized. Valid default inputs work. Missing arguments and native finite-arithmetic overflow/domain failures are preserved.

Direct boolean, nested, string and nonfinite inputs are deliberately refused; nonfinite computed results are refused before public scalar publication. The original overflowing-result control is retained separately. This is explicit finite scalar admission, not an unrestricted malformed-input parity claim or altered wave math. Each dispatch performs only five/six scalar inputs and constant-size arithmetic; no canvas, model or data-dependent iterative workload.

## Verification results

Unique `tests/test_ned_lfo_conversion.py` proves actual all-five registration/schema/proxy, byte-exact original math,12 phase boundaries per ID,300 seeded vectors per ID plus defaults and large/negative controls, exact double bits, malformed/native error controls, two fresh required sandbox guest processes with independently reconstructed pack filesystems and all-five production outer FLOAT outputs, zero-capability execution, source/license/stub/cache identity, exact patch and ZIP reconstructions and wrong-pristine refusal before writes. A test-only public raw-tensor publication probe in the disposable guest runtime is denied without raw authority, followed by valid scalar recovery; that probe is not a released node or a sixth registration.

Run from `v2/tests`:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -B -m pytest -c pytest.ini -p no:cacheprovider test_ned_lfo_conversion.py -q
```

Observed focused checkpoint:110 passed/1 artifact test deselected. The external handoff records final unchanged-byte repeated full results and logs with hashes. Test totals do not imply different nodes or model inference; every named ID has direct and actual-guest behavior evidence.

## Release integrity and dependencies

`secure-nodes.json` binds Python `>=3.13,<3.14`, resolved3.13, zero permissions. No new managed packages or weights are needed; no installation/download occurs. Frozen tested composite SHA-256: Python `89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada`, frontend `2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090`. Optional composite APIs are unused; shared artifacts remain untouched. Source identity and artifact reconstruction have separate proofs.

## Persistence and limitations

No durable state: immutable algorithms with explicit scalar inputs only. Two fresh reconstructed pack filesystems/guest PIDs preserve behavior; no cloud KV or process-global continuation is required or claimed.

Actual macOS required sandbox guests and production outer CPU scalar transport are proved, not Linux/cloud deployment, full downstream animation workflows or user verification. No inference/GPU/credential path exists. Finite scalar admission is an explicit safety narrowing; central integration/release review remains coordinator-owned.
