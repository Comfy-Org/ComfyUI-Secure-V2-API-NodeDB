import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path

import torch


PACKAGE_ROOT = Path(__file__).parents[1]
COMFYUI_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location("image_autosize", PACKAGE_ROOT / "__init__.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ImageAutosizeTests(unittest.TestCase):
	def test_extension_registers_node(self):
		extension = asyncio.run(MODULE.comfy_entrypoint())
		nodes = asyncio.run(extension.get_node_list())

		self.assertEqual(
			nodes,
			[
				MODULE.ImageAutosize,
				MODULE.ImageAutosizeApplyTransform,
				MODULE.ImageAutosizeRestore,
			],
		)

	def test_schema_accepts_images_and_masks(self):
		inputs = MODULE.ImageAutosize.INPUT_TYPES()
		image_options = inputs["required"]["image"][1]
		priority_options = inputs["required"]["constraint_priority"][1]

		self.assertEqual(image_options["template"]["allowed_types"], "IMAGE,MASK")
		self.assertEqual(
			list(inputs["required"]),
			[
				"image",
				"max_size",
				"min_size",
				"divisible_by",
				"interpolation_mode",
				"crop_mode",
				"constraint_priority",
			],
		)
		self.assertEqual(priority_options["options"], ["min_size", "max_size"])
		self.assertEqual(priority_options["default"], "min_size")
		self.assertEqual(MODULE.ImageAutosize.define_schema().display_name, "Image/Mask Autosize")
		self.assertEqual(
			MODULE.ImageAutosize.RETURN_TYPES,
			["COMFY_MATCHTYPE_V3", "INT", "INT", "FLOAT", "FLOAT", "AUTOSIZE_TRANSFORM"],
		)

	def test_autosizes_image_and_reports_pre_crop_scales(self):
		image = torch.zeros((1, 5, 3, 3), dtype=torch.float32)

		output = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="center",
		)

		resized, width, height, scale_x, scale_y = output.args[:5]
		self.assertEqual(resized.shape, (1, 8, 4, 3))
		self.assertEqual((width, height), (4, 8))
		self.assertAlmostEqual(scale_x, 5 / 3)
		self.assertAlmostEqual(scale_y, 8 / 5)

	def test_no_crop_reports_independent_stretch_scales(self):
		image = torch.zeros((1, 5, 3, 3), dtype=torch.float32)

		output = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="none",
		)

		resized, width, height, scale_x, scale_y = output.args[:5]
		self.assertEqual(resized.shape, (1, 8, 4, 3))
		self.assertEqual((width, height), (4, 8))
		self.assertAlmostEqual(scale_x, 4 / 3)
		self.assertAlmostEqual(scale_y, 8 / 5)

	def test_resizes_mask_without_adding_image_channels(self):
		mask = torch.zeros((2, 5, 3), dtype=torch.float32)

		output = MODULE.ImageAutosize.execute(
			image=mask,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="bilinear",
			crop_mode="center",
		)

		resized = output.args[0]
		self.assertEqual(resized.shape, (2, 8, 4))
		self.assertEqual(resized.dtype, mask.dtype)
		self.assertEqual(resized.device, mask.device)

	def test_crops_lanczos_mask_after_grayscale_resize(self):
		mask = torch.zeros((1, 5, 3), dtype=torch.float32)

		output = MODULE.ImageAutosize.execute(
			image=mask,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="lanczos",
			crop_mode="center",
		)

		self.assertEqual(output.args[0].shape, (1, 8, 4))

	def test_avoids_resampling_when_dimensions_are_unchanged(self):
		image = torch.tensor(
			[
				[
					[[0.123456, 0.234567, 0.345678], [0.456789, 0.567891, 0.678912]],
					[[0.789123, 0.891234, 0.912345], [0.135791, 0.246802, 0.357913]],
				],
			],
			dtype=torch.float32,
		)

		output = MODULE.ImageAutosize.execute(
			image=image,
			max_size=2,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=1,
			interpolation_mode="lanczos",
			crop_mode="center",
		)

		self.assertTrue(torch.equal(output.args[0], image))
		self.assertEqual(output.args[3:5], (1.0, 1.0))

	def test_minimum_shorter_dimension_overrides_longer_target(self):
		self.assertEqual(
			MODULE._calculate_target_dimensions(
				width=10,
				height=100,
				max_size=50,
				min_size=10,
				constraint_priority="min_size",
				divisible_by=1,
			),
			(10, 100),
		)

	def test_target_dimensions_cannot_round_to_zero(self):
		width, height = MODULE._calculate_target_dimensions(
			width=1,
			height=100,
			max_size=1,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=32,
		)

		self.assertGreaterEqual(width, 32)
		self.assertGreaterEqual(height, 32)

	def test_maximum_constraint_priority_prefers_smaller_scale(self):
		self.assertEqual(
			MODULE._calculate_target_dimensions(
				width=10,
				height=100,
				max_size=50,
				min_size=10,
				constraint_priority="max_size",
				divisible_by=1,
			),
			(5, 50),
		)

	def test_maximum_constraint_priority_controls_resize(self):
		image = torch.zeros((1, 100, 10, 3), dtype=torch.float32)

		output = MODULE.ImageAutosize.execute(
			image=image,
			max_size=50,
			min_size=10,
			constraint_priority="max_size",
			divisible_by=1,
			interpolation_mode="nearest-exact",
			crop_mode="none",
		)

		resized, width, height, scale_x, scale_y = output.args[:5]
		self.assertEqual(resized.shape, (1, 50, 5, 3))
		self.assertEqual((width, height), (5, 50))
		self.assertEqual((scale_x, scale_y), (0.5, 0.5))

	def test_pad_mode_preserves_content_aspect_and_records_transform(self):
		image = torch.arange(5 * 3 * 3, dtype=torch.float32).reshape(1, 5, 3, 3)

		output = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="pad",
		)

		resized, width, height, scale_x, scale_y, transform = output.args
		self.assertEqual(resized.shape, (1, 8, 4, 3))
		self.assertEqual((width, height), (4, 8))
		self.assertEqual((transform.resize_width, transform.resize_height), (4, 7))
		self.assertEqual((transform.offset_x, transform.offset_y), (0, 0))
		self.assertAlmostEqual(scale_x, 4 / 3)
		self.assertAlmostEqual(scale_y, 7 / 5)

	def test_transform_applies_identical_padding_to_mask(self):
		image = torch.zeros((1, 5, 3, 3))
		mask = torch.ones((1, 5, 3))
		transform = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="pad",
		).args[-1]

		resized_mask, = MODULE.ImageAutosizeApplyTransform.execute(
			mask,
			transform,
			"nearest-exact",
		).args

		self.assertEqual(resized_mask.shape, (1, 8, 4))
		self.assertTrue(torch.all(resized_mask[:, :7] == 1))
		self.assertTrue(torch.all(resized_mask[:, 7:] == 0))

	def test_restore_removes_padding_and_returns_original_dimensions(self):
		image = torch.rand((1, 5, 3, 3))
		resized, *_metadata, transform = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="pad",
		).args

		restored, = MODULE.ImageAutosizeRestore.execute(
			resized,
			transform,
			"nearest-exact",
		).args

		self.assertEqual(restored.shape, image.shape)

	def test_restore_rejects_wrong_canvas_dimensions(self):
		image = torch.zeros((1, 5, 3, 3))
		transform = MODULE.ImageAutosize.execute(
			image=image,
			max_size=8,
			min_size=1,
			constraint_priority="min_size",
			divisible_by=4,
			interpolation_mode="nearest-exact",
			crop_mode="pad",
		).args[-1]

		with self.assertRaisesRegex(ValueError, "transform output dimensions"):
			MODULE.ImageAutosizeRestore.execute(
				torch.zeros((1, 4, 4, 3)),
				transform,
				"nearest-exact",
			)

	def test_crop_origins_follow_selected_anchor(self):
		self.assertEqual(MODULE._get_crop_origin(7, 9, 4, 6, "top_left"), (0, 0))
		self.assertEqual(MODULE._get_crop_origin(7, 9, 4, 6, "bottom_right"), (3, 3))
		self.assertEqual(MODULE._get_crop_origin(7, 9, 4, 6, "top"), (1, 0))
		self.assertEqual(MODULE._get_crop_origin(7, 9, 4, 6, "right"), (3, 1))
		self.assertEqual(MODULE._get_crop_origin(7, 9, 4, 6, "center"), (1, 1))


if __name__ == "__main__":
	unittest.main()
