from dataclasses import dataclass

import torch.nn.functional as F

import comfy.utils
from comfy_api.latest import ComfyExtension, io


SCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
CONSTRAINT_PRIORITIES = ["min_size", "max_size"]
CROP_MODES = [
	"none",
	"pad",
	"center",
	"top",
	"bottom",
	"left",
	"right",
	"top_left",
	"top_right",
	"bottom_left",
	"bottom_right",
]
AUTOSIZE_TRANSFORM = io.Custom("AUTOSIZE_TRANSFORM")


@dataclass(frozen=True)
class AutosizeTransform:
	original_width: int
	original_height: int
	target_width: int
	target_height: int
	resize_width: int
	resize_height: int
	offset_x: int
	offset_y: int
	crop_mode: str


def _calculate_target_dimensions(
	width: int,
	height: int,
	max_size: int,
	min_size: int,
	constraint_priority: str,
	divisible_by: int,
) -> tuple[int, int]:
	max_scale = max_size / max(width, height)
	min_scale = min_size / min(width, height)
	if constraint_priority == "min_size":
		scale = max(max_scale, min_scale)
	else:
		scale = min(min_scale, max_scale)

	target_width = max(divisible_by, round(width * scale / divisible_by) * divisible_by)
	target_height = max(divisible_by, round(height * scale / divisible_by) * divisible_by)
	return target_width, target_height


def _get_crop_origin(
	width: int,
	height: int,
	target_width: int,
	target_height: int,
	crop_mode: str,
) -> tuple[int, int]:
	if crop_mode in ("left", "top_left", "bottom_left"):
		x = 0
	elif crop_mode in ("right", "top_right", "bottom_right"):
		x = width - target_width
	else:
		x = (width - target_width) // 2

	if crop_mode in ("top", "top_left", "top_right"):
		y = 0
	elif crop_mode in ("bottom", "bottom_left", "bottom_right"):
		y = height - target_height
	else:
		y = (height - target_height) // 2

	return x, y


def _to_samples(image):
	is_image = len(image.shape) == 4
	if is_image:
		return image.movedim(-1, 1), True
	return image.unsqueeze(1), False


def _from_samples(samples, is_image):
	if is_image:
		return samples.movedim(1, -1)
	return samples.squeeze(1)


def _resize_samples(samples, width, height, interpolation_mode):
	if samples.shape[-1] == width and samples.shape[-2] == height:
		return samples
	samples = comfy.utils.common_upscale(
		samples,
		width,
		height,
		interpolation_mode,
		"disabled",
	)
	if len(samples.shape) == 3:
		samples = samples.unsqueeze(1)
	return samples


def _apply_transform(image, transform, interpolation_mode):
	samples, is_image = _to_samples(image)
	if samples.shape[-1] != transform.original_width or samples.shape[-2] != transform.original_height:
		raise ValueError(
			"Autosize transform input dimensions must match its source dimensions. "
			f"Expected {(transform.original_width, transform.original_height)}, got "
			f"{(samples.shape[-1], samples.shape[-2])}."
		)

	samples = _resize_samples(
		samples,
		transform.resize_width,
		transform.resize_height,
		interpolation_mode,
	)
	if transform.crop_mode == "pad":
		pad_right = transform.target_width - transform.resize_width - transform.offset_x
		pad_bottom = transform.target_height - transform.resize_height - transform.offset_y
		padding = (transform.offset_x, pad_right, transform.offset_y, pad_bottom)
		if any(padding):
			samples = F.pad(samples, padding, mode="replicate" if is_image else "constant")
	elif transform.crop_mode != "none":
		samples = samples[
			:,
			:,
			transform.offset_y:transform.offset_y + transform.target_height,
			transform.offset_x:transform.offset_x + transform.target_width,
		]
	return _from_samples(samples, is_image)


class ImageAutosize(io.ComfyNode):
	@classmethod
	def define_schema(cls) -> io.Schema:
		image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])

		return io.Schema(
			node_id="ImageAutosize",
			display_name="Image/Mask Autosize",
			category="image",
			description="Automatically resizes an image or mask for diffusion workflows.",
			search_aliases=[
				"autosize",
				"image mask autosize",
				"auto resize",
				"resize to multiple",
				"resize image",
				"resize mask",
			],
			inputs=[
				io.MatchType.Input(
					"image",
					template=image_type,
					tooltip="The image or mask to resize.",
				),
				io.Int.Input(
					"max_size",
					default=1280,
					min=1,
					max=8192,
					step=1,
					tooltip="Longer-dimension target used to calculate one candidate resize scale.",
				),
				io.Int.Input(
					"min_size",
					default=512,
					min=1,
					max=4096,
					step=1,
					tooltip="Shorter-dimension target used to calculate one candidate resize scale.",
				),
				io.Int.Input(
					"divisible_by",
					default=32,
					min=1,
					max=8192,
					step=1,
					tooltip="Rounds both output dimensions to the nearest multiple of this value.",
				),
				io.Combo.Input(
					"interpolation_mode",
					options=SCALE_METHODS,
					default="lanczos",
					tooltip="Interpolation algorithm used for resizing.",
				),
				io.Combo.Input(
					"crop_mode",
					options=CROP_MODES,
					default="center",
					tooltip=(
						"Anchored modes preserve aspect ratio by cropping. Pad preserves aspect ratio "
						"with reversible padding. None stretches to the output dimensions."
					),
				),
				io.Combo.Input(
					"constraint_priority",
					options=CONSTRAINT_PRIORITIES,
					default="min_size",
					tooltip="Chooses the candidate scale. min_size uses the larger scale; max_size uses the smaller scale. Divisibility rounding runs afterward.",
				),
			],
			outputs=[
				io.MatchType.Output(template=image_type, display_name="resized"),
				io.Int.Output(display_name="width"),
				io.Int.Output(display_name="height"),
				io.Float.Output(display_name="scale_x"),
				io.Float.Output(display_name="scale_y"),
				AUTOSIZE_TRANSFORM.Output(display_name="transform"),
			],
		)

	@classmethod
	def execute(
		cls,
		image: io.Image.Type | io.Mask.Type,
		max_size: int,
		min_size: int,
		constraint_priority: str,
		divisible_by: int,
		interpolation_mode: str,
		crop_mode: str,
	) -> io.NodeOutput:
		samples, _is_image = _to_samples(image)
		height, width = samples.shape[-2:]

		target_width, target_height = _calculate_target_dimensions(
			width,
			height,
			max_size,
			min_size,
			constraint_priority,
			divisible_by,
		)

		resize_width = target_width
		resize_height = target_height
		if crop_mode == "pad":
			scale = min(target_width / width, target_height / height)
			resize_width = min(target_width, max(1, round(width * scale)))
			resize_height = min(target_height, max(1, round(height * scale)))
		elif crop_mode != "none":
			scale = max(target_width / width, target_height / height)
			resize_width = max(target_width, round(width * scale))
			resize_height = max(target_height, round(height * scale))

		x = 0
		y = 0
		if crop_mode == "pad":
			x = (target_width - resize_width) // 2
			y = (target_height - resize_height) // 2
		elif crop_mode != "none":
			x, y = _get_crop_origin(
				resize_width,
				resize_height,
				target_width,
				target_height,
				crop_mode,
			)
		transform = AutosizeTransform(
			original_width=width,
			original_height=height,
			target_width=target_width,
			target_height=target_height,
			resize_width=resize_width,
			resize_height=resize_height,
			offset_x=x,
			offset_y=y,
			crop_mode=crop_mode,
		)
		output = _apply_transform(image, transform, interpolation_mode)

		return io.NodeOutput(
			output,
			target_width,
			target_height,
			resize_width / width,
			resize_height / height,
			transform,
		)


class ImageAutosizeApplyTransform(io.ComfyNode):
	@classmethod
	def define_schema(cls) -> io.Schema:
		image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])
		return io.Schema(
			node_id="ImageAutosizeApplyTransform",
			display_name="Apply Autosize Transform",
			category="image",
			inputs=[
				io.MatchType.Input("image", template=image_type),
				AUTOSIZE_TRANSFORM.Input("transform"),
				io.Combo.Input("interpolation_mode", options=SCALE_METHODS, default="nearest-exact"),
			],
			outputs=[io.MatchType.Output(template=image_type, display_name="resized")],
		)

	@classmethod
	def execute(cls, image, transform, interpolation_mode) -> io.NodeOutput:
		return io.NodeOutput(_apply_transform(image, transform, interpolation_mode))


class ImageAutosizeRestore(io.ComfyNode):
	@classmethod
	def define_schema(cls) -> io.Schema:
		image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])
		return io.Schema(
			node_id="ImageAutosizeRestore",
			display_name="Restore Autosized Image/Mask",
			category="image",
			inputs=[
				io.MatchType.Input("image", template=image_type),
				AUTOSIZE_TRANSFORM.Input("transform"),
				io.Combo.Input("interpolation_mode", options=SCALE_METHODS, default="lanczos"),
			],
			outputs=[io.MatchType.Output(template=image_type, display_name="restored")],
		)

	@classmethod
	def execute(cls, image, transform, interpolation_mode) -> io.NodeOutput:
		if transform.crop_mode != "pad":
			raise ValueError("Restore Autosized Image/Mask requires an Autosize transform using pad mode.")

		samples, is_image = _to_samples(image)
		if samples.shape[-1] != transform.target_width or samples.shape[-2] != transform.target_height:
			raise ValueError(
				"Autosized input dimensions must match the transform output dimensions. "
				f"Expected {(transform.target_width, transform.target_height)}, got "
				f"{(samples.shape[-1], samples.shape[-2])}."
			)
		samples = samples[
			:,
			:,
			transform.offset_y:transform.offset_y + transform.resize_height,
			transform.offset_x:transform.offset_x + transform.resize_width,
		]
		samples = _resize_samples(
			samples,
			transform.original_width,
			transform.original_height,
			interpolation_mode,
		)
		return io.NodeOutput(_from_samples(samples, is_image))


class ImageAutosizeExtension(ComfyExtension):
	async def get_node_list(self) -> list[type[io.ComfyNode]]:
		return [ImageAutosize, ImageAutosizeApplyTransform, ImageAutosizeRestore]


async def comfy_entrypoint() -> ImageAutosizeExtension:
	return ImageAutosizeExtension()
