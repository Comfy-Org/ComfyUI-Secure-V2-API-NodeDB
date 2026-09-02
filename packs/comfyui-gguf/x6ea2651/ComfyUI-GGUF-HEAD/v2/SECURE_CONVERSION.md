# Secure Nodes V2 conversion

- Pack: `comfyui-gguf`
- Upstream: `https://github.com/city96/ComfyUI-GGUF`
- Pinned commit: `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`
- Release: `x6ea2651`
- Backend: 6 supported, 0 rejected, 0 pending
- Frontend: 0 supported, 0 rejected, 0 pending

A single aggregate "supported" count would misrepresent this pack, so the
disposition is stated per node instead. Every node the sealed manifest
registers appears in the table below exactly once.

## Per-node disposition

| node_id | class | disposition |
|---|---|---|
| `UnetLoaderGGUF` | `UnetLoaderGGUF` | supported through `ctx.models.load_gguf_model` |
| `UnetLoaderGGUFAdvanced` | `UnetLoaderGGUFAdvanced` | supported through `ctx.models.load_gguf_model` with per-load dtype policy |
| `CLIPLoaderGGUF` | `CLIPLoaderGGUF` | supported through `ctx.models.load_gguf_text_encoders` |
| `DualCLIPLoaderGGUF` | `DualCLIPLoaderGGUF` | supported through `ctx.models.load_gguf_text_encoders` |
| `TripleCLIPLoaderGGUF` | `TripleCLIPLoaderGGUF` | supported through `ctx.models.load_gguf_text_encoders` |
| `QuadrupleCLIPLoaderGGUF` | `QuadrupleCLIPLoaderGGUF` | supported through `ctx.models.load_gguf_text_encoders` |

No node is rejected on policy and no node has pending API work.

## Behavior ledger

All six registered nodes keep their upstream `node_id`, class name, `TITLE`
(as `display_name`), `bootleg` category, widget names and widget order, so no
saved workflow that names them is forked.

`UnetLoaderGGUF` and `UnetLoaderGGUFAdvanced` are supported. Their purpose is
to turn a catalogued quantized diffusion-model file into a MODEL, with an
optional per-load dequantization and patch dtype policy. That is exactly
`ctx.models.load_gguf_model`, so the guest sends a logical catalogue name and
four closed scalars and receives a model ref. No filesystem path, state dict,
`GGMLTensor`, operations class or `ModelPatcher` crosses the boundary. The
advanced node's dtype branch structure is compared value-for-value against
upstream's `load_unet` across all twenty-five widget combinations.

Per-load policy is enforced rather than assumed. Upstream sets dtype attributes
on the nested `GGMLOps.Linear` class, which is one module-global object; the
host instead derives a fresh `Linear` subclass per load. The suite asserts the
dependency's own class is unchanged after two different loads and that no two
loads share a `Linear` object, so one tenant's dtype choice cannot alter
another's concurrent load.

The four CLIP loaders — `CLIPLoaderGGUF`, `DualCLIPLoaderGGUF`,
`TripleCLIPLoaderGGUF`, `QuadrupleCLIPLoaderGGUF` — are supported through
`ctx.models.load_gguf_text_encoders(names: Sequence[str], clip_type: str)`.
Their purpose is to build a CLIP from one to four catalogued text-encoder
files, mixing GGUF and ordinary SafeTensors where upstream permits it. The
guest sends only confined logical names in widget order and a closed CLIP type;
the trusted plane resolves the catalogue entries, loads the state dictionaries,
constructs the CLIP with the fixed GGUF operations, clones its patcher and
returns a CLIP ref. Real guest executions cover all four arities, the two
upstream implicit type defaults, mixed formats, catalogue confinement and
capability refusal.

## Pack algorithms stay in the pack

`dequant.py` and `loader.py` are byte-identical to the pinned upstream tree in
both the pristine and the `v2` copy. None of the quantized tensor math was
moved into core, and the suite asserts core's `_sdk.py` contains no lifted
block-dequantization symbol. Core reaches the algorithm the way it already did
for other packs: by importing this pack as its fixed GGUF vendor module and
calling `gguf_sd_loader`/`GGMLOps`/`GGUFModelPatcher` — from the *installed*
dependency, never from this mirror.

`ops.py` is deliberately NOT shipped in `v2`. Upstream's copy imports
`comfy.ops`, `comfy.lora` and `comfy.model_management`, which is host authority
a converted pack may not carry, and the import-reachability proof below shows
nothing in `v2` can ever load it. It remains untouched in the pristine sibling,
which is the patch base and the vendor module core actually imports, so the
algorithm is not lost — only the unreachable duplicate is dropped.

`loader.py` still carries upstream's `from .ops import GGMLTensor` verbatim.
That import cannot resolve inside `v2` and is never attempted: `loader.py` is
outside the guest import closure, and the suite asserts that every unresolved
pack-relative import is confined to an unreachable module.

Dequantization correctness is verified directly against the `gguf` package's
own numpy reference for all thirteen supported quant types — BF16, Q8_0, Q5_1,
Q5_0, Q4_1, Q4_0, Q6_K, Q5_K, Q4_K, Q3_K, Q2_K, IQ4_NL, IQ4_XS — and, for the
six types the `gguf` package can also quantize, through a real quantize/
dequantize round trip against the source values.

## Model weights

Declaration-only. This pack downloads nothing and declares no weights. Users
supply their own `.gguf` files, which are selected as logical catalogue names
through the closed `/models/gguf/choices` remote route and resolved entirely
in the trusted plane. A selector node never returns a filesystem path, and
`validate_inputs` refuses absolute names, drive-qualified names, traversal
segments and NUL bytes without ever turning a name into a path. GGUF is read by
the pack's own reader; ordinary state dictionaries use the host's restricted
`safe_load=True` path, and scaled-FP8 text encoders are refused because they
cannot safely share the GGUF operations class.

## Frontend

The pinned upstream snapshot ships no `web/` or `js/` directory and registers
no static route, so there is no frontend surface to convert. The mirror
declares no `WEB_DIRECTORY` and no `STATIC_DIRECTORIES`, and the pack loads
with empty static and asset directories and no frontend permissions.

## Host catalogue registration

Upstream mutated `folder_paths.folder_names_and_paths` at module import to add
the `unet_gguf` and `clip_gguf` keys. A guest may not touch the host, so the
mirror DECLARES the mapping as `GGUF_FOLDER_KEYS` in `nodes.py` and the trusted
plane performs the registration. Core's `/models/gguf/choices` route already
degrades to an empty list when the key is absent.

## Security result

Every node requests exactly one capability, `models`, and nothing else. The
pack requests no host filesystem, subprocess, network, secrets, credentials,
output-write, graph-expansion, raw-buffer or runtime-installation authority.
Declaring `models` only asks; the suite asserts that executing with no granted
capability fails closed with a named refusal, that an unknown catalogue name is
refused, and that an absent fixed dependency produces a named runtime error
while the node stays registered.

The authority boundary is proved by import analysis, not by grepping for
substrings. The suite parses every `v2` module with `ast`, starts from the
package entry point plus every module the sealed manifest declares, and walks
`ast.Import`/`ast.ImportFrom` transitively across pack-relative imports to
build the closure of modules a guest can actually load. That closure is exactly
`__init__.py` and `nodes.py`, and no module in it imports `comfy.*`,
`folder_paths`, `nodes`, `torch`, `subprocess`, `requests`, `urllib` or
`socket`, references `__file__`, or calls `open`. `dequant.py` and `loader.py`
are proved to be outside the closure rather than assumed to be, and are
independently checked to carry no host-authority import of their own.

Upstream is Apache-2.0 and the `LICENSE` file is carried through unmodified.
