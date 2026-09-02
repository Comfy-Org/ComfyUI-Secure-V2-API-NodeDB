import { comfy } from '/comfy/api/v2.js';

// Secure Nodes V2 applies this pack's safe compatibility intent natively:
// non-strict COMBO declarations are compatible when their closed value lists
// overlap, while strict prompt validation requires the received list to be a
// subset of the input list.  The legacy pack-wide validate_node_input
// monkeypatch and its mutable HTTP toggle are therefore intentionally absent.
// Keep the import so the module is still evaluated as a V2 extension asset and
// cannot silently fall back to a legacy global.
void comfy;
