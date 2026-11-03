# Secure Nodes V2 conversion: comfyui-dynamicprompts

- Upstream: adieyal/comfyui-dynamicprompts at `3f2fff32358cf39e21b8b440ca87eac9a8e2bade` (version 0.2.1).
- Library: dynamicprompts 0.30.2, the version upstream's requirements.txt pins, with pyparsing 3.3.3
  and PyYAML 6.0.3. A pack dependency profile serves them to the guest (pyproject.toml), and Jinja2
  comes from the guest base.
- The pristine tree and v2/ omit upstream media and example workflows (images/, example_workflows/).

## Nodes
| Node id | Display name | V2 |
|---|---|---|
| DPRandomGenerator | Random Prompts | converted |
| DPCombinatorialGenerator | Combinatorial Prompts | converted |
| DPJinja | Jinja2 Templates | converted |
| DPOutput | OutputString | converted; it fails exactly as upstream does (below) |
| DPMagicPrompt | Magic Prompt | refused by name |
| DPFeelingLucky | I'm Feeling Lucky | refused by name |

All six keep their original inputs, options, outputs, categories and display names.

## How it runs
- The node modules in `nodes/` are byte-identical copies. The V2 classes in `_secure_dp.py` call them.
- `nodes/__init__.py` imports nothing. The original imported all six node modules there, and
  `magicprompt.py` imports transformers at module import.
- Random Prompts and Combinatorial Prompts keep one original instance per workflow node id and node
  type, for the life of the pack's guest process. That is the per-node state Core keeps for a V1 node.
  The iterator, the current template and the wildcard tree carry over between runs. A seed above 0
  reseeds the library's shared random generator before each run, as before.
- Wildcards: the original read ComfyUI/wildcards from the host file system, or the pack's own
  wildcards folder when that one was missing. V2 reads the `dynamicprompts_wildcards` asset kind
  through the SDK when a node instance is created. The library then builds its wildcard tree from
  those files with its own code, so all its rules apply unchanged:
  - .txt, .json and .yaml files are read, and directories starting with "." are skipped;
  - comment and blank lines are dropped;
  - weights and JSON/YAML structure are honoured.
- DPJinja makes a new instance per run, as the original's state-free node allows.
- DPOutput upstream always fails: its method takes `string`, but its input is named `text`. V2 calls the
  same method the same way, so it fails with the same TypeError.

## Refused
Both refusals show at queue time (`validate_inputs`) and in `execute`:
- DPMagicPrompt: "comfyui-dynamicprompts/DPMagicPrompt is not yet converted to Secure Nodes V2: it
  rewrites prompts with a GPT-2 text-generation model, which this pack's guest does not have"
- DPFeelingLucky: "comfyui-dynamicprompts/DPFeelingLucky is not yet converted to Secure Nodes V2: it
  fetches prompts from an online search service at run time, and a Secure Nodes V2 guest has no network"

## Known differences
1. **No wildcard asset kind.** A run that samples a wildcard fails with `WildcardsUnavailableError`,
   which names the kind, when the host has no `dynamicprompts_wildcards` asset kind or its listing
   fails (the SDK lists at most 4096 names). Runs that sample no wildcard are unaffected.
2. **When files are read.** V2 reads the wildcard files when a node instance is created. The original
   read them at the first wildcard it sampled, so only the original sees a change made in between.
3. **Instance lifetime.** Core drops a V1 node's instance when a prompt runs without that node, but v2
   keeps it until the pack's guest process ends. So after such a prompt, the original restarts the
   node's combinatorial sequence and re-reads wildcards, while v2 continues. A guest restart resets
   every node, like a server restart.
4. **Wildcard name collisions.** When two files give the same wildcard name (for example colors.txt
   and a colors.json list), the later file wins in both. The original's order is the host file
   system's directory order; v2's is sorted.
5. **Frontend file and installer.** `web-extensions/dp.js` is not served. install.py copied it into
   ComfyUI's web/extensions to redefine a PROMPT widget type that no node in this pack uses, and
   install.py is never run.
6. **Shared random streams.** Unseeded draws are random in both, from different streams: Jinja's
   choice/random/randint use the guest's own `random` module, and the guest has its own copy of the
   library's shared generator.

DPJinja renders with a non-sandboxed Jinja2 environment, as upstream does. In V2 that rendering
happens inside the guest.

## Parity
`tests/test_dynamicprompts_parity.py` runs in the lane gate with the pinned wheels. It compares the
original pack under Core with these classes, run by run, over synthetic wildcard fixtures.
