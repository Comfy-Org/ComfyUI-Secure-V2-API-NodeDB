import torch

class MaskBatchMerge: #Add Mode

    CATEGORY = "mmmmmmmmm"
    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("merged_mask",)
    FUNCTION = "merge_masks"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask_batch": ("MASK",),
            }
        }

    def merge_masks(self, mask_batch):

        # 1. Sum from dim=0
        merged = torch.sum(mask_batch, dim=0, keepdim=True)
        
        # 2. Limit the value between 0-1, in case of exposure after adding
        merged = torch.clamp(merged, 0.0, 1.0)
        
        return (merged,)

NODE_CLASS_MAPPINGS = {
    "MaskBatchMergeAdd": MaskBatchMerge
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskBatchMergeAdd": "Mask Merger"
}