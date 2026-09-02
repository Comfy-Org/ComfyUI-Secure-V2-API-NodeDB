# Secure Nodes V2 conversion ledger

Pinned source: `38e89f95671e1dcdca86c9baf57ac2e1cb2f89e1`.

## Backend

All 11 intended registered node types are supported:

- `LoraLoaderVanilla`
- `LoraLoaderStackedVanilla`
- `LoraLoaderAdvanced`
- `LoraLoaderStackedAdvanced`
- `LoraTagsOnly`
- `Randomizer`
- `FusionText`
- `TextInputBasic`
- `TagsSelector`
- `TagsFormater`
- `LoraListNames`

The two Advanced IDs intentionally remain distinct registered contracts even
though upstream aliases them to the corresponding Vanilla implementation.

## Frontend

The one upstream extension registration resolves to six supported behaviors,
enumerated by `FRONTEND_INTENTS` in `web/autotrigger.js`:

- list, subfolder-tree, and thumbnail-grid display modes;
- host-rendered hierarchical LoRA catalogue grouping and filtering;
- managed adjacent LoRA image/video previews;
- live preview lookup after model-definition refreshes;
- normalization of object-valued combo selections;
- assigning the currently displayed managed output as a selected LoRA preview.

## Authority changes

- LoRA names are logical entries in the host's confined `loras` catalogue;
  the guest never receives a path.
- Safetensors metadata is parsed from a bounded header range. LoRA weights do
  not enter the guest; the opaque model operation loads and applies them on the
  trusted side with safe weight loading.
- Civitai access uses the fixed, bounded vendor namespace. `force_fetch`
  bypasses the trusted vendor cache; projected `trainedWords` are cached in the
  host's pack-and-tenant-scoped bounded storage.
- Preview assignment passes only model value, source node ID, and image index.
  The host resolves the managed output, confines and re-encodes it, writes the
  adjacent preview atomically, and refreshes model definitions.
- This pack declares no Hugging Face weights and performs no model downloads.

Rejected: none. Pending API gaps: none.
