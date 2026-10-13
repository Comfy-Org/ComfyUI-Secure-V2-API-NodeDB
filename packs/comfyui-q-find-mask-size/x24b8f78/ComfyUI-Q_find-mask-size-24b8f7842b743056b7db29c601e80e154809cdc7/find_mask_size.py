import torch
import numpy as np
from PIL import Image

class QImageCropCalculator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "step_size": ("INT", {"default": 8, "min": 4, "max": 128, "step": 4}),
                "padding": ("INT", {"default": 8, "min": 0, "max": 256, "step": 2}),
                "min_size": ("INT", {"default": 520, "min": 128, "max": 4096, "step": 8}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT")
    RETURN_NAMES = ("width", "height", "x_offset", "y_offset")
    FUNCTION = "calculate_optimal_crop"
    CATEGORY = "image/crop"

    def calculate_optimal_crop(self, mask, step_size=32, padding=64, min_size=256):
        """
        Oblicza optymalny rozmiar przycięcia na podstawie maski
        """
        
        # Konwersja maski z ComfyUI tensor do numpy
        if isinstance(mask, torch.Tensor):
            mask_np = mask[0].cpu().numpy()
        else:
            mask_np = mask
            
        # Znajdź wszystkie niepuszczególne piksele (wartości > 0)
        non_zero_coords = np.where(mask_np > 0.1)
        
        if len(non_zero_coords[0]) == 0:
            # Brak obiektu w masce - zwróć minimalny rozmiar wyśrodkowany
            height, width = mask_np.shape
            crop_width = min_size
            crop_height = min_size
            x_offset = max(0, (width - crop_width) // 2)
            y_offset = max(0, (height - crop_height) // 2)
            return (crop_width, crop_height, x_offset, y_offset)
        
        # Znajdź bounding box obiektu
        min_y, min_x = np.min(non_zero_coords[0]), np.min(non_zero_coords[1])
        max_y, max_x = np.max(non_zero_coords[0]), np.max(non_zero_coords[1])
        
        # Dodaj padding
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(mask_np.shape[1], max_x + padding)
        max_y = min(mask_np.shape[0], max_y + padding)
        
        # Oblicz wymiary z paddingiem
        object_width = max_x - min_x
        object_height = max_y - min_y
        
        # Użyj większego wymiaru jako bazę i zrób kwadrat
        base_size = max(object_width, object_height)
        
        # Zaokrąglij do najbliższego step_size
        crop_size = ((base_size + step_size - 1) // step_size) * step_size
        
        # Upewnij się, że nie jest mniejszy niż min_size
        crop_size = max(crop_size, min_size)
        
        # Oblicz kwadratowy crop wyśrodkowany na obiekcie
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        
        # Oblicz offset tak, żeby crop był wyśrodkowany na obiekcie
        x_offset = max(0, min(center_x - crop_size // 2, mask_np.shape[1] - crop_size))
        y_offset = max(0, min(center_y - crop_size // 2, mask_np.shape[0] - crop_size))
        
        # Jeśli obraz jest mniejszy niż crop_size, dostosuj
        final_width = min(crop_size, mask_np.shape[1])
        final_height = min(crop_size, mask_np.shape[0])
        
        return (int(final_width), int(final_height), int(x_offset), int(y_offset))