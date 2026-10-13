# JSON Helper — exact Git V2 source conversion

Selected full Git baseline: `23b7bad7c112dfad9140d5754ba1f6ef50ee720a`, upstream
https://github.com/a-und-b/ComfyUI_JSON_Helper. All eight tracked blobs, modes
and original project version1.0.0 are preserved in the pristine sibling,
including tracked node.zip. This is the coordinator's explicit selection.

The related official Registry1.0.1 archive is separate evidence, not the source
baseline or a Git-equality claim: six files match but project version differs
and the archive omits node.zip. Earlier release-only intake/source controls are
preserved outside this selected snapshot. No source pin was invented.

The one original node ID/class JSONStringToObjectNode, display JSON String to
Object, multiline STRING input and custom JSON output are retained. Missing
CATEGORY and output-name fields retain native sd/JSON defaults; it is not an
output node. No frontend, routes, models, files, network, user persistence or
private dependencies exist. Zero capabilities and SDK_REFS=True are declared.

The original710B json parser module is copied byte-identically, and V2 entry
returns io.NodeOutput around its unchanged native tuple. Every JSON root is
retained. JSONDecodeError prints the original message and returns None; other
native exceptions propagate. No input/root/depth/length/nonfinite bounds or
normalization are introduced. The SDK/transport's actual rules remain its own.

V2 pyproject preserves1.0.0 and adds>=3.13,<3.14 matching manifest resolved3.13.
The unchanged actual runtime declaration decoder is tested on this selected
metadata. Earlier eight source controls passed twice on the identical parser
and adapter. Their release1.0.1 metadata check is separately attributed; the
selected Git metadata receives a new focused check, with no old behavior replay.
The initial recursion-threshold assumption was corrected only in the test;
its RED evidence and production bytes remain intact.

Canonical pair and apply roundtrip are bound by the owned PAIR_PROOF.json.
Native Git0755/0644 modes and V2 source modes are recorded separately from
Windows0777 observations. Git-mode preservation is not runtime admission.

Actual installed SDK/schema/manifest decoding, JSON data wire behavior (including
nonfinite, large/deep and lone-surrogate values), printed diagnostic fidelity,
registered managed execution and complete independent cleanup remain pending.
The future registered test is authored/unrun. One backend remains pending full
acceptance; rejected/count delta0. No generator/shared/runtime/profile work is
included, and no standing runtime reservation exists.
