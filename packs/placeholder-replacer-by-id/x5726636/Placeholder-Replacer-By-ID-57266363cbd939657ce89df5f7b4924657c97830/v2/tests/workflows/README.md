Register the productionv2 and separate test-oracle-r1/v2 extension in ephemeral
draftTEST. Every JSON file here is a raw API graph. Built-ins only EmptyImage
with literal64x64/batch1/color0x223344 and PreviewImage. Typed producer sends one
INT_LIST list as plain data, never OUTPUT_IS_LIST or INPUT_IS_LIST. The real
registered converter receives that typed edge and each3STRING output goes to
the strict oracle. Exact output types/strings/debug text/Unicode are checked
against native reference results encoded inside one JSONSTRING. An independent
ImageRef passes unchanged to PreviewImage only after assertions succeed.
Observe executed strict-oracle receipt with passed:true and all3exactstrings;
independentPNG alone is not converter-output evidence. The typed uint64 values
are JSONSTRING payloads, avoiding JS Number rounding. Submit filebytes exactly.
Oracle and producer compare their actual installed encode_schema to serialized
schemas; oracle also canonical-encodes an exact production schema body fixture.
This confirms source schema compatibility, not actual installed production
identity: manager must separately compare actual registered producer/converter
schema and selected published contracts. Original full class/helpers/process
remain unchanged;3.13target runtime controls are distinct from worker3.12checks.
Native empty-delimiter/unconditional-manual-parser failures must occur atnode2;
intentional wrong-debug must fail atnode4. All3must produce0previewartifacts,
then run golden-default-0 for actual service recovery. Successful cases each
render1PNG64x64. No worker SDK/guest/job; actual runtime belongs to MERVYN.
Remaining native error/cache/lifetime/intake gates stay explicit; no inputcaps.
