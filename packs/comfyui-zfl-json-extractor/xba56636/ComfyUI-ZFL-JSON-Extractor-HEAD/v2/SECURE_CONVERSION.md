# Source-only scalar mirror

Upstream: xufengbo1993/ComfyUI-ZFL-JSON-Extractor@ba56636a11365da1d025c3a1688b37dbd9cd0530. Whole registered set: 1 IDs.

The public io.ComfyNode adapter keeps IDs, class names, display/category, input ordering, declared metadata, outputs and list/UI flags. Schemas use inert literals; compute calls the retained original class method once. SDK_REFS=True and SDK_PERMISSIONS=() because all registered inputs/outputs are plain scalars.

Pristine upstream files are unchanged. CaptainGrock alone renames its standalone file to an importable guest-local _original.py and removes only AST-proven unused math/random/torch imports; class and method bodies remain exact.

No supplied pack/SDK/helper/test/generator code has been run or imported here. Native/default/real Guest comparisons, normal full-ID manifest, canonical pair and two pristine replays are future selected execution stages. Source review and actual runtime binding are pending; no runtime, publication or acceptance credit.
