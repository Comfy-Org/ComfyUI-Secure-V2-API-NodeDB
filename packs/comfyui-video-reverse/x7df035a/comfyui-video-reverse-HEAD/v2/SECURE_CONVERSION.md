Purpose: return video frames in reverse batch order.

Adapter for sean-bradley/comfyui-video-reverse at
7df035a64a11a0ab78547158a58f048b7e0ef02f (v1.0.0). The node ID,
display name, SBCODE category, required IMAGE frames input and IMAGE frames
output are unchanged. No route, model, filesystem or network capability is
requested.

The complete original __init__.py is bundled byte-exact as _upstream.py and
imported only during execute. The adapter materializes the input through
public ImageRef.raw(), invokes the original reverse method, and publishes a
changed result through public ImageRef.from_value(). Original passthrough
returns retain their input ref. The original frame flip and messages remain
in the original module. define_schema uses literals and imports no upstream
module.

The required raw permission is a request, not a grant. Ref lifetime remains
owned by the execution runtime. No SDK private member or generated stub is
used by the production adapter.

The selected CPU component attempt on 2026-10-26 passed 24 valid IMAGE
cases through the full original module, stock default SDK dispatcher and one
real required Seatbelt Guest: 72 positive calls. Cases cover batch 1/4,
channels 1..4 and float32/float64/uint8. The existing float32 RGB batch-4
strided-width case passed strict original/default/Guest envelope, type,
shape, frame-order and value checks first, recording 1/1/1 calls before the
remaining 23 cases. All calls preserve the input; outputs match the genuine
original frame reversal.

Eight separate original/public-factory boundary diagnostics have zero Guest
equivalence credit. The public IMAGE factory requires nonempty BHWC; batch
zero and malformed publication remain outside that contract. Four actual
wrong-result controls (frame order, dtype, shape and pixel) were detected.
One normal manifest generation retained the original VideoReverseNode ID
and raw permission only. Canonical pair/bundle application, two pristine
byte-and-mode replays and two changed-base refusal controls passed.

The retained Mac profile 40fbb95d729e2f10ba9c7809fa08135f5d9f433372d41d2d9d044cd58a68cdaf
uses Python 3.13.14, torch 2.13.0 and numpy 2.4.6. Normal-site runtime startup
and the required Guest were observed; runtime=None and no native Guest
fallback were used. Bounds were 120 seconds from OWNER_STARTED after config
(initial pre-config guard 150 seconds), 90 seconds of work, 15 seconds cleanup,
2 GiB sampled descendant RSS, 512 KiB payload reports/captures and zero retry.
Owner elapsed time was 35.498 seconds, sampled descendant peak RSS
500842496 bytes. These are sampled/task guards, not OS quotas.

All six independent before/after maps and four owner map joins matched.
The assigned Guest birth joined PID, PPID, actual PGID, UID, start and SID
between the journal owner and independent passive witness. All eight
recorded PIDs, four actual groups, socket and socket directory were absent
in two terminal readbacks. The owner temporary root retained only an empty
home directory; no sockets remained. Stderr retained two existing torch
pynvml deprecation warnings. No monitor or cleanup errors occurred.

Qualification authority: m_891023df15. Full immutable evidence archive:
ca26db9692660df7f49977161b8fced57642789624fc149a0a2eca065ea0fa28.
Independent result intake, reported by the coordinator: review
7709f2064fd9fff8516bd669162aa0b1cf439ba8aa01a028ed39ff48a9d00325.
The publication stage retains every tested executable file and the exact
generated one-ID/raw-only manifest. Relative to the tested 22-file V2 tree,
it updates this report and adds the two existing canonical generated authoring
declarations, for 24 V2 files. Neither declaration was generated or edited here:
Python comfy-api.pyi: 42b9ec2d9f7db0190c39fe5207c4253aaf04ec7851a52cb59c6e667a538478a7;
TypeScript comfy-api.d.ts: abf1417d3d2fa5edf993fbf1965c3df4386ea27bf357264bc0588fa5bb5099d2.
Their retained authoring provenance uses the exact f1 SDK runtime, 0fa public
facade and 56fe IO implementation pins recorded in AUTHORING_API_ORIGINS.json.
The declarations already provide ImageRef.raw and ImageRef.from_value; they
are authoring files, not runtime implementations. Canonical pair/bundle
metadata and two pristine replays with changed-base controls were repeated
for this packaging delta. No manifest regeneration, node rerun, SDK or
scientific execution occurred during publication preparation.

Credit is limited to CPU IMAGE tensor reversal and source generation/replay.
Whole workflows, browser behavior, video-container decoding/encoding,
model execution, managed services and service acceptance remain untested.
The process observations are not an exhaustive transient census and do not
close the pre-fsync observation gap.
