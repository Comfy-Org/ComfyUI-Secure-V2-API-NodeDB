import torch
import numpy as np
class LoaderCrop:

    def crop_center(self, image, target_size=224):
        h, w = (image.shape[1], image.shape[2])
        crop_size = min(h, w)
        y = (h - crop_size) // 2
        x = (w - crop_size) // 2
        cropped = image[:, y:y + crop_size, x:x + crop_size, :]
        return cropped

    def crop_mask(self, image, mask, target_size=None):
        if mask.shape[1:3] != image.shape[1:3]:
            mask = torch.nn.functional.interpolate(mask.unsqueeze(1), size=(image.shape[1], image.shape[2]), mode='bilinear', antialias=False).squeeze(1)
        if mask.device.type != 'cpu':
            mask_np = mask[0].cpu().numpy()
        else:
            mask_np = mask[0].numpy()
        y_indices, x_indices = np.where(mask_np > 0.05)
        if len(y_indices) == 0 or len(x_indices) == 0:
            return self.crop_center(image)
        y1, y2 = (np.min(y_indices), np.max(y_indices))
        x1, x2 = (np.min(x_indices), np.max(x_indices))
        cropped = image[:, y1:y2, x1:x2, :]
        return cropped
