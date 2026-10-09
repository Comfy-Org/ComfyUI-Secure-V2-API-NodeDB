# Basic Math 0.0.6 — bounded local conversion

All 23 source IDs are retained. There are no frontend entries, routes,
model/service dependencies, external resources, or durable/per-node state.
`math_nodes.py`, `tools.py`, `base_node.py` and the MIT LICENSE stay byte-identical.
V3 wrappers retain source input order/types/options, output tokens/names,
categories/display names, VariantSupport validation, native algorithms and bare
exception defaults. The classic V3 projection spells implicit empty options as
`{}` and represents ordered combo choices as COMBO/options with multiselectFalse;
all choices/defaults and authored options remain exact. Source pyproject's missing LICENSE.txt
reference is retained as provenance; the real LICENSE is packaged unchanged.

Permission set is empty. SDK value mode handles only admitted plain data; no
raw permission, host-object reconstruction, tensor access, or private imports.
Each execution preflights exact built-in scalar/list/tuple/dict trees, depth16,
4096 cumulative items including keys, and 64KiB conservative escaped formatting
work. Scalar integers are at most2048 bits on input and4096 bits on output.
IEEE NaN/infinity/signed zero are preserved, not sanitized. Opaque refs,
subclasses, cycles and unsupported wire dictionary keys are outside this
profile. No source repr/truth promise exists for host objects. Plain values
must additionally fit the public wire's existing dictionary-key envelope.

Power, multiplication, addition/subtraction and left shifts have conservative
projected integer-bit guards before source operations. Decimal rounding admits
absolute decimals <=1000. Conservative formatting work is metered before
`str`/casts; output is independently metered. Profile refusals are outside
source catches: they never masquerade as zero/False/NaN. Native errors/defaults
for admitted work remain unchanged, including negative shifts/exponents and
division/modulo-by-zero behavior.

Regex uses original Python3.13 `re.match`, after the source's actual lowercase
normalization. Subject<=8192 code points; pattern<=1024 UTF8 bytes; parsed
tokens<=256/depth<=16. Admit consuming literal/class/category/dot atoms,
anchors, plain groups and at most one repeat of one consuming atom, with finite
repeat bounds<=8192. No branch, repeated compound group, nested/nullable
repeat, backreference or lookaround. Valid unadmitted syntax visibly refuses;
bounded malformed native syntax still follows source False behavior. No
substitute engine, altered flags, search-for-match substitution, or hidden
literal reinterpretation. The one-repeat profile bounds native backtracking
by finite subject/pattern products; it is not a native heap/CPU hard-profile
attestation. Surrogate/Unicode/case/zero-width controls compare the real engine.

Tests cover all node defaults/options, native type/error quirks and validators,
source identity, oversize pre-operation/format sentinels, required Seatbelt
fresh guest execution and true production outer outputs, refusal/recovery,
manifest/census and exact pristine/V2 plain+ZIP reconstruction/tamper refusal.
Caller supplies COMFY_CORE_ROOT and BASIC_MATH_BACKEND_ROOT; test runtime
fingerprints fail on drift rather than using historical absolute paths.

Evidence is Python3.13 Mac development execution, not sealed native provisioning,
Linux/Cloud deployment or permission expansion. Whole/local acceptance and
counts belong to the coordinator's independent intake, not aggregate totals.
