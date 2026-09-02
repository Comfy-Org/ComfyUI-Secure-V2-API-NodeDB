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
