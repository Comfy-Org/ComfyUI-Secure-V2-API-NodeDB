# Finding 3: optional sockets the converted schema doesn't declare (facts for the reviewer)

This note was gathered statically at corpus main `a45522ff`; nothing was run. The LoRA subtree is unchanged at
`e18b3c87`. r2 and r3 don't touch sockets, so the facts below are unchanged.

**Status after the independent review (LORA10-N1, r3).** This is a schema/type-validation gap. A prompt rejection has
**not** been demonstrated.
- **Supporting core source** (a snapshot, not a measurement of the deployed core:
  `coordination/aux-transport-completion-20261016/runtime-source/core/execution.py` in Root's workspace):
  - `get_input_data` passes a linked value for any input, declared or not, and accepts other values when the v3 class
    sets `ACCEPT_ALL_INPUTS` (lines 284-303).
  - `validate_inputs` checks only the declared required and optional inputs (from line 1239).
- **So** the undeclared `lora_stack` and `prev_hooks` values reach `execute` through `**kwargs` without declared type
  validation. Omitting them doesn't by itself reject the prompt.
- **Not fixed in r3.** Closing B1 doesn't need it, and option (B) means a schema edit plus a manifest regenerated in the
  established approved environment, which is outside this PC.
- **Held.** Actual linked-chain qualification stays under the existing runtime/window hold.

## What rev 10 does

- **Lora Stacker.** `text_row_sync.js` (`NATIVE_SOCKETS` and `attach`) adds `lora_stack` (LORA_STACK, optional), but
  only once the Stacker's `text`/`loras` widgets exist, which means r4a.
  - It first checks that any reconstructed socket of that name is unique and of type LORA_STACK; otherwise it throws
    before changing anything.
  - On live nothing is added: the Stacker stays `text`, `loras` sockets, as on main (test L5).
  - Tests R5 and R10 cover the r4a case.
- **Lora Loader.** The same check finds the declared `clip` and `lora_stack` and adds nothing (test R1).
- **Create Hook LoRA, the same pattern.** Rev 10 registers main's `create_hook_lora.js`. Its `planCreateHookInput` adds
  `prev_hooks` (HOOKS, optional) **on live and r4a alike**, after the same kind of check (test L6).

## Original (upstream x2dcaf6a)

- `web/comfyui/lora_stacker.js:17-24`: `onNodeCreated` sets `serialize_widgets = true` and
  `addInput("lora_stack", "LORA_STACK", { shape: 7 })`.
- `web/comfyui/lora_loader.js:176-187`: the same for `clip` and `lora_stack`.
- `py/nodes/lora_stacker.py`: `INPUT_TYPES` declares `text` and `loras`, plus `FlexibleOptionalInputType(any_type)`.
  The socket comes from the frontend.
- Workflows the original saved carry these sockets:
  - `example_workflows/nunchaku-flux.1-dev.json`: the Stacker inputs are `text`, plus `lora_stack` (LORA_STACK, shape 7).
  - The Loader in both example workflows has `clip` and `lora_stack` (shape 7).

## Converted backend (main a45522ff)

| Node | Schema | Inputs declared | Reads |
|---|---|---|---|
| Lora Loader | `secure_loader_nodes.py:16-25` (blob `e6a87580`) | `model`, `text`, `loras`, `clip` (optional), `lora_stack` (optional); `accept_all_inputs=True` | `execute(cls, model, text, loras, clip=None, lora_stack=None, **kwargs)` |
| Lora Stacker | `secure_stack_nodes.py:12-19` (blob `8284de01`) | `text`, `loras`; `accept_all_inputs=True` | `execute(cls, text, loras, **kwargs)` reads `kwargs.get('lora_stack')` (line 28) |
| Create Hook LoRA | `secure_hook_node.py:15-16` (blob `d9a2c1f6`) → `secure_remaining_schemas.py:54-61` (`create_hook_schema`; its `text` tooltip says "Hooks chain with prev_hooks.") | `text`, `loras`; `accept_all_inputs=True` | `execute(cls, text, loras, **kwargs)` reads `kwargs.get('prev_hooks')` (line 25) |

The two loaders are converted differently:
- **Lora Loader:** its optional sockets are declared.
- **Lora Stacker and Create Hook:** each consumes its socket's value without declaring it, through
  `accept_all_inputs`. The socket exists only if a frontend adds it or a saved workflow reconstructs it.

`secure-nodes.json` (blob `ee8bf587`) matches the schemas.
- **Stacker row:** 2 inputs. **Create Hook row:** `text`, `loras`.
- **Loader `lora_stack` entry:**
  `{"attrs":{"advanced":null,"display_name":null,"extra_dict":{},"id":"lora_stack","lazy":null,"optional":true,"rawLink":null,"tooltip":null},"io_type":"LORA_STACK","kind":"standard"}`.

## The two options

**(A) Keep the sockets frontend-added**, which is rev 10 as drafted and frontend-only.
- This is upstream's own mechanism.
- New Stackers get `lora_stack` only with rev 10 on r4a. Create Hook gets `prev_hooks` with rev 10 on both hosts.
- The values reach `execute` through `accept_all_inputs`. These are the same paths main's backend relies on today.
- Prompt validation (per the core source above) passes these undeclared linked values through without type-checking them,
  so the cost of (A) is the missing declared type validation, not a rejected prompt.

**(B) Declare the sockets in the schema**, like the Loader.
- **Code.**
  - `secure_stack_nodes.py`: add `io.Custom('LORA_STACK').Input('lora_stack', optional=True)` after `loras`, and take
    `lora_stack=None` in `execute`. Behaviour is otherwise unchanged.
  - `create_hook_schema`: add the same `prev_hooks` (HOOKS, optional) input.
- **Manifest.**
  - The Stacker row gains one entry of the Loader's form.
  - The Create Hook row gains a HOOKS entry.
  - Earlier manifest row changes were checked against the backend encoders in a selected bounded run (rev 8,
    `SECURE_CONVERSION.md` line 95).
  - Regenerating the manifest means running the backend manifest generator, and that is not run on this PC (no SDK
    imports here).
- **Effect.**
  - The host creates the sockets from the definition on every host, with no frontend.
  - Prompt validation sees declared optional inputs.
  - Rev 10's socket checks find them and add nothing, as they do for the Loader. Rev 10's Stacker entry in
    `NATIVE_SOCKETS` becomes a no-op guard.
  - LORA_STACK and HOOKS are sockets, not widget types, so declaring them doesn't move `widgets_values`.
  - Original-saved workflows carry sockets of the same name and type (above), so reconstruction should line up. BART's
    S12 loads `nunchaku-flux.1-dev.json`, whose Stacker has one.
