import torch
import numpy as np
import torch
import cv2

class MaskToBottonHalfConvexMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("MASK",)
    CATEGORY = "MaskToBottonHalfConvexMask"
    FUNCTION = "generate_convex_mask"

    def generate_convex_mask(self, mask):
        """
        生成一个凸形遮罩，填充输入遮罩下半部分的凹区域。
        
        参数：
            mask (torch.Tensor): 输入遮罩，尺寸为 (batch_size, height, width)。
        
        返回：
            torch.Tensor: 生成的凸形遮罩，尺寸与输入遮罩相同。
        """
        # 将 PyTorch 张量转换为 NumPy 数组
        mask_np = mask.squeeze(0).numpy()  # 去掉 batch_size 维度

        height, width = mask_np.shape
        bottom_half = mask_np[height // 2:, :]
        contours, _ = cv2.findContours(
            bottom_half.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if len(contours) == 0:
            return (mask,)

        all_points = np.vstack(contours)
        # 计算凸包
        hull = cv2.convexHull(all_points)
        # 创建一个空白图像用于绘制凸包
        convex_mask = np.zeros_like(bottom_half, dtype=np.float32)
        # 填充凸包区域
        cv2.fillPoly(convex_mask, [hull], 1.0)

        new_mask = mask_np.copy()
        new_mask[height // 2:, :] = convex_mask

        new_mask_tensor = torch.from_numpy(new_mask).unsqueeze(0)  # 添加 batch_size 维度

        return (new_mask_tensor,)


class MaskToConvexMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),  # 输入的 MASK
            },
        }
    
    RETURN_TYPES = ("MASK",)
    CATEGORY = "MaskToConvexMask"
    FUNCTION = "generate_convex_mask"

    def generate_convex_mask(self, mask):
        """
        将输入的 MASK 的凹区域填充为凸区域。
        
        参数：
            mask (torch.Tensor): 输入的 MASK，形状为 (batch_size, height, width)。
        
        返回：
            torch.Tensor: 新的 MASK，形状为 (batch_size, height, width)。
        """
        mask_np = mask.squeeze(0).numpy()  # 去掉 batch_size 维度

        contours, _ = cv2.findContours(
            mask_np.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if len(contours) == 0:
            return (mask,)

        all_points = np.vstack(contours)
        # 计算凸包
        hull = cv2.convexHull(all_points)
        # 创建一个空白图像用于绘制凸包
        convex_mask = np.zeros_like(mask_np, dtype=np.float32)
        # 填充凸包区域
        cv2.fillPoly(convex_mask, [hull], 1.0)
        convex_mask_tensor = torch.from_numpy(convex_mask).unsqueeze(0)  # 添加 batch_size 维度

        return (convex_mask_tensor,)