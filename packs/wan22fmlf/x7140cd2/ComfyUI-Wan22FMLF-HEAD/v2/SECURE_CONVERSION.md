# Secure Nodes V2 conversion

- Pack: `wan22fmlf`
- Upstream: `https://github.com/wallen0322/ComfyUI-Wan22FMLF`
- Pinned commit: `7140cd224396aff9fd909ab0041c3fbf81b92b0c`
- Release: `x7140cd2`
- Backend: 8 supported, 0 rejected, 0 pending
- Frontend: 1 supported, 0 rejected, 0 pending

## Behavior ledger

The five Wan conditioning nodes retain the pinned pack's frame alignment,
reference placement, centered resize, high/low-noise masks, selective image
conditioning, structural-repulsion gradients, latent continuation, SVI overlap,
motion/detail decay, trim counts, next-offset calculation, and CLIP Vision
aggregation. The latent and image tail extractors retain their exact slicing
and zero-frame behavior. These algorithms remain in the guest and are checked
against the pristine implementations with exact tensor comparisons.

Core provides only the generic building blocks those algorithms require:
brokered tensor values, VAE encoding, bounded VAE latent-layout metadata,
CLIP Vision output concatenation, and attachment of one CLIP Vision output to
a conditioning value. No Wan conditioning, masking, stage, motion, or SVI
algorithm was moved into core.

The multi-image loader retains its indexed gallery behavior and its original
black-image fallback for empty, malformed, missing, or invalid identities. It
accepts no absolute path or traversal. An identity is resolved through the
asset broker and only that brokered file's bytes are decoded inside the guest.
Capability denial is not converted into a dummy success; it fails closed.

## Frontend

The gallery retains replace/add selection, bounded sequential upload, preview,
thumbnail selection, deletion, explicit ordering, two-step clear, workflow
restore, serialization, and cleanup. The browser owns file selection through
`comfy.files.pickMany` with limits of 50 images, 16 MiB per image, and 256 MiB
total. Upload and preview use the fixed `/upload/image` and `/view` routes.

The extension imports only `/comfy/api/v2.js`, creates UI through the node
widget mount, derives its document from the supplied container, and runs with
no ambient `window`, `document`, legacy app object, unrestricted fetch, parent
realm, or same-origin iframe grant. Both a document-free VM and the real
allow-scripts-only iframe/worker bridge exercise the gallery.

## Security result

The seven tensor-processing nodes request only `raw`. The loader requests only
`assets` and `raw`. The pack requests no host filesystem, subprocess, network,
secrets, credentials, model-download, output-write, graph-expansion, or runtime
installation authority. It declares no additional weights and performs no
download. All eight backend nodes and the one frontend extension are supported;
no intended behavior is rejected or pending.

The pinned upstream snapshot contains no license declaration. This conversion
records that fact and does not infer a license.
