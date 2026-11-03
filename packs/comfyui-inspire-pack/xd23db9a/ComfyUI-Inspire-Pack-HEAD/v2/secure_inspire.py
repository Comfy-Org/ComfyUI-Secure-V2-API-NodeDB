"""Secure Nodes V2 registration of ComfyUI-Inspire-Pack (pin d23db9aa, version 1.23).

Converted, with the original ids, schemas and display names:
- round 1: LoadImagesFromDir //Inspire, LoadImageListFromDir //Inspire, ChangeImageBatchSize //Inspire
  (_sn_image.py);
- round 2: GlobalSeed //Inspire (_sn_global_seed.py; its seed control is web/global_seed.js).

The pack's other declared nodes are not registered in this round (see SECURE_CONVERSION.md).
"""

from ._sn_global_seed import GlobalSeed
from ._sn_image import ChangeImageBatchSize, LoadImagesFromDirBatch, LoadImagesFromDirList

NODE_CLASS_MAPPINGS = {
    "LoadImagesFromDir //Inspire": LoadImagesFromDirBatch,
    "LoadImageListFromDir //Inspire": LoadImagesFromDirList,
    "ChangeImageBatchSize //Inspire": ChangeImageBatchSize,
    "GlobalSeed //Inspire": GlobalSeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImagesFromDir //Inspire": "Load Image Batch From Dir (Inspire)",
    "LoadImageListFromDir //Inspire": "Load Image List From Dir (Inspire)",
    "ChangeImageBatchSize //Inspire": "Change Image Batch Size (Inspire)",
    "GlobalSeed //Inspire": "Global Seed (Inspire)",
}
