> INPROGRESS: finite native/default-SDK component and authoring evidence passed; Guest, public executor and whole-pack acceptance remain open.

# Secure Nodes V2 conversion — RandomSeedGenerator

Upstream: <https://github.com/Limbicnation/ComfyUI-RandomSeedGenerator>

Pinned commit: `ec04f6748e0aa57ea5165baa149188eedb5980b8` (`xec04f67`).

The pack declares one original node, `AdvancedSeedGenerator`. Its fixed, random,
increment and decrement computation, unsigned 64-bit wraparound, reset helper and
cache fingerprint contract have bounded native evidence. This does not complete
the pack's behavior across public dispatches, renders, the frontend or Guest
processes. No node is formally refused by this revision.

## Current finite evidence

One Root-selected R3 attempt, `m_3b921d8105`, passed 101 generation observations:
97 exact integer returns and four exact original `ValueError` class/message
matches for unknown modes. The frozen matrix includes values around 2^53 and the
full uint64 maximum, both native instances, shared-counter updates, wraparound
and interleaved fixed reads. Python JSON integers retain their exact values.
Complete original/candidate RNG states, counters and outcomes agree.

Nineteen fingerprint observations comprise seven exact fixed strings and twelve
dynamic timestamps inside each side's own real wall-clock bracket. Dynamic
timestamps are not required to be identical. Forty-six separate reset-helper
observations preserve RNG and reset both class counters to zero. Six separate
comparator controls detect wrong seed, counter, RNG, complete error, fixed
fingerprint and dynamic time range; they are not security-boundary tests.
Twenty-two complete RNG-state records are retained and hash-bound.

The full frozen original and converted packages were normally imported using
genuine stdlib `random` and `time` and the qualified default SDK. No random/time
provider was replaced. Valid fixture setup and restoration deliberately control
class state in one native interpreter. The original class counter is shared
across instances; this evidence does not establish per-node isolation or
class-state continuity between Guest jobs, public dispatches, frontend actions
or renders. Those purposes remain unqualified, rather than silently assumed.

## Schema and authoring artifacts

The actual normalized V3 callable exposes one INT output, exact integer maximum
`18446744073709551615`, `SDK_REFS=false` and an empty permission list. One genuine
normal generation ran in the R3 job. Its manifest is
`3df9592f4949b1d8b5861c335d3605a85cd67a4c0fef044f332dc39187f104d9`.
Relative to the saved template `2ca7d06e`, it adds only the current schema field
`loop_boundary: null`. The manifest is therefore changed and is not claimed
semantically identical to the old template. Node identity, input/output contract,
permissions and production computation are preserved.

Six serial logical stages used one actual worker: native sequences/schema/
fingerprints/controls, normal generation, canonical generation, bundle creation
and two pristine replays. The changed-base control refused the intentional
original-source mismatch without adding V2 outputs. All eleven original files
and executable production bytes remained unchanged. Publication separately
regenerates the canonical pair for this truthful report using only the pinned
stdlib file tool, and repeats file-only pristine/changed-base checks. It adds no
normal generation, node, SDK, scientific, native or Guest run.

## Exact runtime, ownership and retirement

The selected Python 3.13.14 profile is
`40fbb95d729e2f10ba9c7809fa08135f5d9f433372d41d2d9d044cd58a68cdaf`,
Core `44564d0279c275eef52b11750a9d76349f4e7a88`, backend
`59bd3e1acba6520bb32717ad03833f6ab2967ecc`, SDK engine `f1a73e4f` and
public facade `0fa03049`. Complete before/after maps are byte-identical:
45 input leaves, 84,917 site leaves, 96 component leaves, and the full runtime
and seven operator/config records. Actual runtime pins cover 141 SDK,
1,384 Core and 83 backend leaves; backend83 and component96 are distinct.

Actual external/native/worker exits were zero. The native owner took
40.388544708 seconds; external time recorded 40.47 seconds. Its 97 durable
journal events contain the creation/adoption lineage, 16 RSS samples and 14
paired absence probes. There were no monitor, probe, cleanup, signal or deadline
errors. Five actual task PIDs and three groups were independently absent twice.
The empty socket observations cover only the owned temporary tree. The public
retirement record is explicitly derived task-only evidence; private raw host
inventories and journals remain retained and hash-bound.

The reviewed owner finalized its queue state with `queue_state_restored=true`
and no failed-cleanup hold branch. No independent post-terminal queue-file
snapshot is retained; this is owner/source-bound restoration, not an independent
queue readback or authorization for another job. Normal sole-worker retirement
was exercised. Live cancellation, surviving descendants, probe failures,
terminal-write failures, timeout and memory-trigger cleanup remain unqualified.

Sampled aggregate peak RSS was 1,157,152,768 bytes, including the native controller
and its witnessed descendants. External owner maxRSS 958,971,904 bytes is a
separate observation. The sampled 2 GiB watchdog, one-thread settings and
userspace deadlines are not hard memory, CPU or wall-clock quotas. Nominal
reclaimable capacity is not a reservation or model-fit proof.

## Preserved history and remaining gates

R1 remains FAILED, with its exact failed probe target, interruption cause and
aggregate RSS UNKNOWN. Its immutable strict receipt begins `28c132f5`. R2 stayed
source-only and unrun. R3 is one separately selected attempt without automatic
retries; its success neither repairs the R1 record nor diagnoses that failure.

Strict R3 receipt:
`1281e5d2b5981e7b694f8845bc2cdc816e954b47213b8f75e0e68f15ae894934`.
Private raw archive:
`6ec8761acfc20d95f2b7da6a10a1045b1d9e34a68065ccc7089e883ff8984ccb`.
Compact evidence lives under `validation/20261020-randomseed-native-r3/`.

The node declares no refs, permissions, dependencies, HTTP, routes, models or
UI extension. This source declaration is separate from live admission. No model
inference, managed dependency-closure, public executor, Guest, frontend,
cross-render state-continuity, shared-service or whole-pack acceptance is
claimed. Root retains source publication and every later execution/admission
decision.
