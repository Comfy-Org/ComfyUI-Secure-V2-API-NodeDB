# Secure Nodes V2 conversion ledger

Pinned source: `ebe75a158b8c19d69a5e4e24c1f25085babda5b4`.

## Backend

All 26 intended registered node types are supported:

- `iToolsLoadImagePlus`
- `iToolsPromptLoader`
- `iToolsPromptSaver`
- `iToolsAddOverlay`
- `iToolsLoadImages`
- `iToolsPromptStyler`
- `iToolsPromptStylerExtra`
- `iToolsGridFiller`
- `iToolsLineLoader`
- `iToolsTextReplacer`
- `iToolsKSampler`
- `iToolsVaePreview`
- `iToolsCheckerBoard`
- `iToolsLoadRandomImage`
- `iToolsPreviewText`
- `iToolsRegexNode`
- `iToolsPreviewImage`
- `iToolsCompareImage`
- `iToolsPromptRecord`
- `iToolsInstructorNode`
- `iToolsPromptBuilder`
- `iToolsImageAdjust`
- `iToolsPaintNode`
- `iToolsCropImage`
- `iToolsTestNode`
- `iToolsDomNode`

The two Together.ai classes in the source are not part of the registered pack
surface: upstream hard-codes `allow_experimental_nodes = False` before the
conditional that would register them.

## Frontend

The 20 upstream extension registrations and the separately registered prompt
sidebar resolve to 21 supported behaviors. They are enumerated by
`FRONTEND_INTENTS` in `web/itools.js` and exercised in both worker-shaped and
allow-scripts iframe-shaped harnesses.

## Authority changes

- File and directory inputs are confined to managed `input`, `output`, `temp`,
  and declared read-only pack assets.
- Prompt saving appends only below managed `output` or `temp`.
- Paint and crop state travels as the node's bounded serialized widget data;
  it is never staged through pack-global files or custom HTTP routes.
- RMBG-2.0 is a hash-pinned, on-demand Hugging Face weight. The trusted model
  broker downloads it once into its cache and reuses it on later executions.
- Prompt-library state uses the pack's storage namespace. Explicit bounded host
  pickers/downloads replace ambient filesystem and browser-storage access.

Rejected: none. Pending API gaps: none.

## Repair r1

- **Prompt Styler Extra follows the original's text exactly.** `combine_multi` and
  `get_template_value_from_yaml_file` are ported line for line, and only the two file reads go through the
  asset broker. That covers three things:
  - the original's placeholder clean-up has no effect, so the second to fourth templates keep their
    `{prompt}` text;
  - template names in `used_templates` have `" | "` and `" > "` compacted;
  - templates are looked up by name among entries that have a prompt, in `styles/` and then
    `styles/more examples/`.
- **Style menus.** The node declares the original's validator for its four style inputs. A style chosen
  from a file other than the default is therefore accepted, as in the original. The file menus are still
  checked.

## Repair r2

- **Prompt Styler follows the original exactly.** It runs `read_replace_and_combine`, ported line for line,
  with only the file reads going through the asset broker; Prompt Builder's merge uses it too. That covers:
  - "none" returns `(file:none)` with the cleaned text, before anything is read;
  - entries named none, random or increment, and entries without a prompt, are skipped;
  - a template without `{prompt}` is appended as `text, template`;
  - the "not found" message is the original's.
- **Template menu.** The node declares the original's validator for `template_name`. A template from a file
  other than `basic.yaml` is therefore accepted, as in the original. The file menu is still checked.

## Dependency profile (NED profile r1): pyyaml 6.0.3
- A production guest sees only its sealed lock, the pack's runtime base and its declared dependency profile, not
  Core's requirements. Base 0cd9adec has no pyyaml.
- `nodes.py` imports `yaml` when it loads, so without a profile no row of this pack loads.
- `pyproject.toml` pins `pyyaml==6.0.3` for the pack's profile (cp313 manylinux wheel, PyPI sha256
  0f29edc409a6392443abf94b9cf89ce99889a1dd5376d94316ae5145dfedd5d6).
- `secure-nodes.json` gains `runtime.dependencies.profile_sha256` when the profile is built.
- `tests/test_itools_yaml_profile.py` hides every yaml except the pinned one under /deps. Without it every row
  fails to load; with it every row loads, and the Prompt Styler equals the original in a real guest.
