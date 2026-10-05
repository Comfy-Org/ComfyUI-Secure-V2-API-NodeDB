import copy
import logging
import math

import torch


FLOAT_TENSOR_SCOPE_ALL = "all_float_tensors"
FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA = "main_conditioning_and_float_metadata"
FLOAT_TENSOR_SCOPE_MAIN_ONLY = "main_conditioning_only"
FLOAT_TENSOR_SCOPE_METADATA_ONLY = "float_metadata_only"
FLOAT_TENSOR_SCOPE_CHOICES = [
	FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA,
	FLOAT_TENSOR_SCOPE_MAIN_ONLY,
	FLOAT_TENSOR_SCOPE_METADATA_ONLY,
	FLOAT_TENSOR_SCOPE_ALL,
]

NON_FLOAT_BEHAVIOR_PRESERVE = "preserve"
NON_FLOAT_BEHAVIOR_ERROR = "error"
NON_FLOAT_BEHAVIOR_CHOICES = [
	NON_FLOAT_BEHAVIOR_PRESERVE,
	NON_FLOAT_BEHAVIOR_ERROR,
]

CURVE_LINEAR = "linear"
CURVE_COSINE = "cosine"
CURVE_SMOOTHSTEP = "smoothstep"
CURVE_EASE_IN = "ease_in"
CURVE_EASE_OUT = "ease_out"
CURVE_SIGMOID = "sigmoid"
CURVE_CHOICES = [
	CURVE_LINEAR,
	CURVE_COSINE,
	CURVE_SMOOTHSTEP,
	CURVE_EASE_IN,
	CURVE_EASE_OUT,
	CURVE_SIGMOID,
]

OUTSIDE_WINDOW_HOLD = "hold"
OUTSIDE_WINDOW_BASELINE = "baseline"
OUTSIDE_WINDOW_LINEAR_EXTRAPOLATE = "linear_extrapolate"
OUTSIDE_WINDOW_CHOICES = [
	OUTSIDE_WINDOW_HOLD,
	OUTSIDE_WINDOW_BASELINE,
	OUTSIDE_WINDOW_LINEAR_EXTRAPOLATE,
]

TIMESTEP_EPSILON = 1e-5


def _path_matches_metadata_key(path, metadata_keys):
	if not path:
		return False
	last_key = path[-1]
	return isinstance(last_key, str) and last_key in metadata_keys


def _is_main_conditioning_tensor_path(path):
	if len(path) == 1:
		return path[0] == 0
	return len(path) == 2 and isinstance(path[0], int) and path[1] == 0


def _should_multiply_float_tensor(path, tensor_scope, metadata_keys):
	is_main_conditioning = _is_main_conditioning_tensor_path(path)
	is_selected_metadata = _path_matches_metadata_key(path, metadata_keys)

	if tensor_scope == FLOAT_TENSOR_SCOPE_ALL:
		return True
	if tensor_scope == FLOAT_TENSOR_SCOPE_MAIN_ONLY:
		return is_main_conditioning
	if tensor_scope == FLOAT_TENSOR_SCOPE_METADATA_ONLY:
		return is_selected_metadata
	return is_main_conditioning or is_selected_metadata


def _multiply_structure(
	structure,
	multiplier,
	tensor_scope,
	non_float_behavior,
	metadata_keys,
	path=(),
	stats=None,
):
	if stats is None:
		stats = {
			"multiplied": 0,
			"preserved_non_float": 0,
			"preserved_float": 0,
		}

	if isinstance(structure, torch.Tensor):
		if structure.is_floating_point() or structure.is_complex():
			if _should_multiply_float_tensor(path, tensor_scope, metadata_keys):
				stats["multiplied"] += 1
				return structure * multiplier
			stats["preserved_float"] += 1
			return structure

		if non_float_behavior == NON_FLOAT_BEHAVIOR_ERROR:
			raise TypeError(
				"ConditioningMultiplyAdvanced refused to multiply non-floating tensor "
				f"at path {'.'.join(map(str, path)) or '<root>'} with dtype {structure.dtype}."
			)
		stats["preserved_non_float"] += 1
		return structure

	if isinstance(structure, list):
		return [
			_multiply_structure(
				item,
				multiplier,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				path + (index,),
				stats,
			)
			for index, item in enumerate(structure)
		]

	if isinstance(structure, tuple):
		return tuple(
			_multiply_structure(
				item,
				multiplier,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				path + (index,),
				stats,
			)
			for index, item in enumerate(structure)
		)

	if isinstance(structure, dict):
		return {
			key: _multiply_structure(
				value,
				multiplier,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				path + (key,),
				stats,
			)
			for key, value in structure.items()
		}

	return copy.deepcopy(structure)


def _parse_metadata_keys(metadata_keys):
	if not isinstance(metadata_keys, str):
		return set()
	return {
		key.strip()
		for key in metadata_keys.split(",")
		if key.strip()
	}


def _clamp_percent(value):
	return max(0.0, min(1.0, float(value)))


def _curve_weight(percent, curve):
	percent = _clamp_percent(percent)

	if curve == CURVE_LINEAR:
		return percent
	if curve == CURVE_SMOOTHSTEP:
		return percent * percent * (3.0 - 2.0 * percent)
	if curve == CURVE_COSINE:
		return 0.5 - 0.5 * math.cos(math.pi * percent)
	if curve == CURVE_EASE_IN:
		return percent * percent
	if curve == CURVE_EASE_OUT:
		return 1.0 - (1.0 - percent) * (1.0 - percent)
	if curve == CURVE_SIGMOID:
		return 1.0 / (1.0 + math.exp(-10.0 * (percent - 0.5)))

	raise ValueError(f"Unknown curve: {curve}")


def _lerp(start, end, weight):
	return (1.0 - weight) * start + weight * end


def _windowed_multiplier(
	percent,
	start_multiplier,
	end_multiplier,
	start_percent,
	end_percent,
	curve,
	outside_window,
):
	denominator = max(TIMESTEP_EPSILON, end_percent - start_percent)
	unbounded_percent = (percent - start_percent) / denominator

	if start_percent <= percent <= end_percent:
		return _lerp(start_multiplier, end_multiplier, _curve_weight(unbounded_percent, curve))

	if outside_window == OUTSIDE_WINDOW_BASELINE:
		return 1.0
	if outside_window == OUTSIDE_WINDOW_LINEAR_EXTRAPOLATE:
		return _lerp(start_multiplier, end_multiplier, unbounded_percent)
	if percent < start_percent:
		return start_multiplier
	return end_multiplier


def _copy_conditioning_entry_with_values(entry, values):
	if len(entry) < 2 or not isinstance(entry[1], dict):
		return copy.deepcopy(entry)

	metadata = entry[1].copy()
	metadata.update(values)
	return [entry[0], metadata]


def _get_conditioning_range(entry):
	if len(entry) < 2 or not isinstance(entry[1], dict):
		return 0.0, 1.0
	return (
		_clamp_percent(entry[1].get("start_percent", 0.0)),
		_clamp_percent(entry[1].get("end_percent", 1.0)),
	)


def _append_scaled_range(
	out,
	entry,
	range_start,
	range_end,
	multiplier,
	tensor_scope,
	non_float_behavior,
	metadata_keys,
	stats,
):
	if range_start >= range_end:
		return

	scaled_entry = _multiply_structure(
		entry,
		float(multiplier),
		tensor_scope,
		non_float_behavior,
		metadata_keys,
		stats=stats,
	)
	out.append(_copy_conditioning_entry_with_values(scaled_entry, {
		"start_percent": range_start,
		"end_percent": range_end,
	}))


def _append_segmented_range(
	out,
	entry,
	range_start,
	range_end,
	segments,
	start_multiplier,
	end_multiplier,
	start_percent,
	end_percent,
	curve,
	outside_window,
	tensor_scope,
	non_float_behavior,
	metadata_keys,
	stats,
):
	if range_start >= range_end:
		return

	segments = max(1, int(segments))
	span = range_end - range_start
	for segment_index in range(segments):
		segment_start = range_start + span * (segment_index / segments)
		segment_end = range_start + span * ((segment_index + 1) / segments)
		if segment_index < segments - 1:
			segment_end = max(segment_start, segment_end - TIMESTEP_EPSILON)

		midpoint = (segment_start + segment_end) * 0.5
		multiplier = _windowed_multiplier(
			midpoint,
			start_multiplier,
			end_multiplier,
			start_percent,
			end_percent,
			curve,
			outside_window,
		)
		_append_scaled_range(
			out,
			entry,
			segment_start,
			segment_end,
			multiplier,
			tensor_scope,
			non_float_behavior,
			metadata_keys,
			stats,
		)


def _multiply_conditioning_with_schedule(
	conditioning,
	start_multiplier,
	end_multiplier,
	start_percent,
	end_percent,
	curve,
	outside_window,
	segments,
	tensor_scope,
	non_float_behavior,
	metadata_keys,
	stats,
):
	start_percent = _clamp_percent(start_percent)
	end_percent = _clamp_percent(end_percent)
	segments = max(1, int(segments))

	if (
		abs(float(start_multiplier) - float(end_multiplier)) <= 1e-12
		and (
			outside_window == OUTSIDE_WINDOW_HOLD
			or (start_percent <= 0.0 and end_percent >= 1.0)
		)
	):
		return _multiply_structure(
			conditioning,
			float(start_multiplier),
			tensor_scope,
			non_float_behavior,
			metadata_keys,
			stats=stats,
		)

	if start_percent >= end_percent:
		logging.warning(
			"ConditioningMultiplyAdvanced: start_percent must be lower than end_percent; "
			"returning unchanged conditioning."
		)
		return conditioning

	out = []
	for entry in conditioning:
		conditioning_start, conditioning_end = _get_conditioning_range(entry)
		intersect_start = max(start_percent, conditioning_start)
		intersect_end = min(end_percent, conditioning_end)

		if conditioning_start < start_percent:
			before_end = min(conditioning_end, max(conditioning_start, start_percent - TIMESTEP_EPSILON))
			before_segments = segments if outside_window == OUTSIDE_WINDOW_LINEAR_EXTRAPOLATE else 1
			_append_segmented_range(
				out,
				entry,
				conditioning_start,
				before_end,
				before_segments,
				start_multiplier,
				end_multiplier,
				start_percent,
				end_percent,
				curve,
				outside_window,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				stats,
			)

		if intersect_start < intersect_end:
			_append_segmented_range(
				out,
				entry,
				intersect_start,
				intersect_end,
				segments,
				start_multiplier,
				end_multiplier,
				start_percent,
				end_percent,
				curve,
				outside_window,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				stats,
			)

		if end_percent < conditioning_end:
			after_start = max(conditioning_start, min(conditioning_end, end_percent + TIMESTEP_EPSILON))
			after_segments = segments if outside_window == OUTSIDE_WINDOW_LINEAR_EXTRAPOLATE else 1
			_append_segmented_range(
				out,
				entry,
				after_start,
				conditioning_end,
				after_segments,
				start_multiplier,
				end_multiplier,
				start_percent,
				end_percent,
				curve,
				outside_window,
				tensor_scope,
				non_float_behavior,
				metadata_keys,
				stats,
			)

	return out


class ConditioningMultiplyAdvanced:
	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"conditioning": ("CONDITIONING", {
					"tooltip": "Conditioning payload to scale."
				}),
				"start_multiplier": ("FLOAT", {
					"default": 1.0,
					"min": -1000000000.0,
					"max": 1000000000.0,
					"step": 0.01,
					"round": False,
					"tooltip": "Multiplier used at start_percent and before the window when outside_window is hold."
				}),
				"end_multiplier": ("FLOAT", {
					"default": 1.0,
					"min": -1000000000.0,
					"max": 1000000000.0,
					"step": 0.01,
					"round": False,
					"tooltip": "Multiplier used at end_percent and after the window when outside_window is hold."
				}),
				"start_percent": ("FLOAT", {
					"default": 0.0,
					"min": 0.0,
					"max": 1.0,
					"step": 0.001,
					"tooltip": "Denoise progress where the multiplier transition window starts."
				}),
				"end_percent": ("FLOAT", {
					"default": 1.0,
					"min": 0.0,
					"max": 1.0,
					"step": 0.001,
					"tooltip": "Denoise progress where the multiplier transition window ends."
				}),
				"curve": (CURVE_CHOICES, {
					"default": CURVE_LINEAR,
					"tooltip": "Curve used to interpolate from start_multiplier to end_multiplier inside the timestep window."
				}),
				"outside_window": (OUTSIDE_WINDOW_CHOICES, {
					"default": OUTSIDE_WINDOW_HOLD,
					"tooltip": "hold uses start_multiplier before the window and end_multiplier after it. baseline uses 1.0 outside the window. linear_extrapolate continues a linear multiplier trend outside the window."
				}),
				"segments": ("INT", {
					"default": 16,
					"min": 1,
					"max": 256,
					"step": 1,
					"tooltip": "Number of conditioning ranges used to approximate the multiplier curve inside the window."
				}),
				"tensor_scope": (FLOAT_TENSOR_SCOPE_CHOICES, {
					"default": FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA,
					"tooltip": "Controls which floating tensors are multiplied. The default scales the main conditioning tensor plus selected float metadata such as pooled_output and t5xxl_weights."
				}),
				"non_float_behavior": (NON_FLOAT_BEHAVIOR_CHOICES, {
					"default": NON_FLOAT_BEHAVIOR_PRESERVE,
					"tooltip": "preserve leaves integer/bool tensors unchanged. error raises when a non-floating tensor is encountered."
				}),
				"metadata_keys": ("STRING", {
					"default": "pooled_output,t5xxl_weights",
					"multiline": False,
					"tooltip": "Comma-separated metadata tensor keys to scale when tensor_scope includes metadata. Integer token ids such as t5xxl_ids should not be listed."
				}),
				"log_summary": ("BOOLEAN", {
					"default": False,
					"tooltip": "Print how many tensors were multiplied or preserved."
				}),
			}
		}

	RETURN_TYPES = ("CONDITIONING",)
	RETURN_NAMES = ("conditioning",)
	FUNCTION = "multiply"
	CATEGORY = "advanced/conditioning"
	DESCRIPTION = "Multiply selected floating conditioning tensors while preserving integer token-id tensors such as Anima t5xxl_ids."
	SEARCH_ALIASES = ["multiply conditioning", "scale conditioning", "conditioning strength", "prompt strength"]

	def multiply(
		self,
		conditioning,
		start_multiplier,
		end_multiplier,
		start_percent,
		end_percent,
		curve,
		outside_window,
		segments,
		tensor_scope=FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA,
		non_float_behavior=NON_FLOAT_BEHAVIOR_PRESERVE,
		metadata_keys="pooled_output,t5xxl_weights",
		log_summary=False,
	):
		if tensor_scope not in FLOAT_TENSOR_SCOPE_CHOICES:
			tensor_scope = FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA
		if non_float_behavior not in NON_FLOAT_BEHAVIOR_CHOICES:
			non_float_behavior = NON_FLOAT_BEHAVIOR_PRESERVE
		if curve not in CURVE_CHOICES:
			curve = CURVE_LINEAR
		if outside_window not in OUTSIDE_WINDOW_CHOICES:
			outside_window = OUTSIDE_WINDOW_HOLD

		stats = {
			"multiplied": 0,
			"preserved_non_float": 0,
			"preserved_float": 0,
		}
		out = _multiply_conditioning_with_schedule(
			conditioning,
			float(start_multiplier),
			float(end_multiplier),
			start_percent,
			end_percent,
			curve,
			outside_window,
			segments,
			tensor_scope,
			non_float_behavior,
			_parse_metadata_keys(metadata_keys),
			stats,
		)

		if log_summary:
			logging.info(
				"ConditioningMultiplyAdvanced: "
				f"multiplied={stats['multiplied']} "
				f"preserved_float={stats['preserved_float']} "
				f"preserved_non_float={stats['preserved_non_float']} "
				f"scope={tensor_scope} "
				f"start_multiplier={float(start_multiplier):.4g} "
				f"end_multiplier={float(end_multiplier):.4g} "
				f"start_percent={_clamp_percent(start_percent):.3f} "
				f"end_percent={_clamp_percent(end_percent):.3f} "
				f"curve={curve} "
				f"outside_window={outside_window} "
				f"segments={max(1, int(segments))}"
			)

		return (out,)


NODE_CLASS_MAPPINGS = {
	"ConditioningMultiplyAdvanced": ConditioningMultiplyAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
	"ConditioningMultiplyAdvanced": "Conditioning Multiply Advanced",
}

__all__ = [
	"NODE_CLASS_MAPPINGS",
	"NODE_DISPLAY_NAME_MAPPINGS",
]
