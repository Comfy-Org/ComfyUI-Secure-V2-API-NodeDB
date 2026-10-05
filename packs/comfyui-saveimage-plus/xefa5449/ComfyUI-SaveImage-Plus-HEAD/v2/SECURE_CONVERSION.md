# Secure Nodes V2 conversion

Upstream: `https://github.com/Goktug/comfyui-saveimage-plus`

Pinned commit: `efa54493216e47126e022a6a38cdaf0c0480256d`

The Python node preserves PNG, JPEG, lossless WebP, and lossy WebP output,
including the original compression/quality choices and optional workflow
metadata. Output is confined to the host output broker.

The frontend preserves bounded JPEG/WebP workflow and prompt import through a
typed workflow importer. It no longer patches ComfyUI's global file handler or
ambient file input, and has no direct DOM, filesystem, or network authority.
