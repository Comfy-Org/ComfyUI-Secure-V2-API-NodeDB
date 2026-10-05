import unittest

import cv2
import numpy as np
import torch

from mosaic_masking import GRID_DIR, MosaicMask


class MosaicMaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = MosaicMask()

    def test_batch_output_uses_comfy_mask_contract(self):
        image = torch.zeros((2, 64, 64, 3), dtype=torch.float32)

        result = self.node.get_mask(image, top_n=1, kernel_size=0)

        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0].shape, (2, 64, 64))
        self.assertEqual(result[0].dtype, torch.float32)
        self.assertTrue(torch.all((result[0] >= 0) & (result[0] <= 1)))

    def test_detects_grid_without_implicit_dilation(self):
        canvas = np.full((128, 128), 255, dtype=np.uint8)
        grid = cv2.imread(str(GRID_DIR / "pattern15x15.png"), cv2.IMREAD_GRAYSCALE)
        height, width = grid.shape
        canvas[40 : 40 + height, 50 : 50 + width] = grid
        image = torch.from_numpy(np.repeat(canvas[..., None], 3, axis=-1)).unsqueeze(0).float() / 255

        mask_zero = self.node.get_mask(image, top_n=1, kernel_size=0)[0]
        mask_one = self.node.get_mask(image, top_n=1, kernel_size=1)[0]

        self.assertGreater(torch.count_nonzero(mask_zero).item(), 0)
        self.assertTrue(torch.equal(mask_zero, mask_one))
        self.assertEqual(set(torch.unique(mask_zero).tolist()), {0.0, 1.0})

    def test_keeps_only_largest_components(self):
        mask = np.zeros((32, 32), dtype=np.uint8)
        mask[1:4, 1:4] = 1
        mask[10:20, 10:20] = 1

        result = self.node.keep_largest_component(mask, top_n=1)

        self.assertEqual(int(result.sum()), 100)


if __name__ == "__main__":
    unittest.main()
