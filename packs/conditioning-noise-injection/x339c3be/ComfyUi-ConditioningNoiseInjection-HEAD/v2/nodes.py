"""Secure conditioning-noise injection."""

from __future__ import annotations

import math
from typing import Any

import torch

from comfy_api.latest import ComfyExtension, io, sdk


MAX_CONDITIONING_ROWS = 64
MAX_METADATA_ITEMS = 256
MAX_TENSOR_ELEMENTS = 268_435_456
MAX_PROMPT_NODES = 10_000
MAX_BATCH = 256
MAX_SEED = 0xFFFFFFFFFFFFFFFF
BOUNDARY_EPSILON = 1e-3


def _prompt_mapping(prompt: Any) -> dict[Any, Any]:
    if isinstance(prompt, tuple) and len(prompt) >= 2:
        prompt = prompt[1]
    if not isinstance(prompt, dict) or len(prompt) > MAX_PROMPT_NODES:
        return {}
    return prompt


def _linked_node(prompt: dict[Any, Any], value: Any) -> dict[str, Any] | None:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    node_id = value[0]
    node = prompt.get(node_id, prompt.get(str(node_id)))
    return node if isinstance(node, dict) else None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value if minimum <= value <= maximum else default


def workflow_parameters(prompt: Any) -> tuple[int, int]:
    """Find the first active sampler using the legacy extension's precedence."""

    graph = _prompt_mapping(prompt)
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        node_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(node_type, str) or not isinstance(inputs, dict):
            continue

        if node_type == "SamplerCustomAdvanced":
            noise_node = _linked_node(graph, inputs.get("noise"))
            noise_inputs = noise_node.get("inputs", {}) if noise_node else {}
            seed = noise_inputs.get("seed", noise_inputs.get("noise_seed", 0))
            latent_node = _linked_node(graph, inputs.get("latent_image"))
            latent_inputs = latent_node.get("inputs", {}) if latent_node else {}
            batch = latent_inputs.get("batch_size", 1)
            return (
                _bounded_int(seed, 0, 0, MAX_SEED),
                _bounded_int(batch, 1, 1, MAX_BATCH),
            )

        if node_type in ("KSampler", "KSamplerAdvanced"):
            if _linked_node(graph, inputs.get("model")) is None:
                continue
            seed = inputs.get("seed", inputs.get("noise_seed", 0))
            latent_node = _linked_node(graph, inputs.get("latent_image"))
            latent_inputs = latent_node.get("inputs", {}) if latent_node else {}
            batch = latent_inputs.get("batch_size", 1)
            return (
                _bounded_int(seed, 0, 0, MAX_SEED),
                _bounded_int(batch, 1, 1, MAX_BATCH),
            )

    return 0, 1


def _intersection(
    metadata: dict[str, Any], limit_start: float, limit_end: float,
) -> tuple[float, float]:
    old_start = metadata.get("start_percent", 0.0)
    old_end = metadata.get("end_percent", 1.0)
    if not isinstance(old_start, (int, float)) or not math.isfinite(old_start):
        raise ValueError("conditioning start_percent must be finite")
    if not isinstance(old_end, (int, float)) or not math.isfinite(old_end):
        raise ValueError("conditioning end_percent must be finite")
    new_start = max(float(old_start), limit_start)
    new_end = min(float(old_end), limit_end)
    return (1.0, 0.0) if new_start >= new_end else (new_start, new_end)


def inject_noise(
    conditioning: list[Any], threshold: float, strength: float,
    seed: int, batch_size: int,
) -> list[list[Any]]:
    threshold = round(threshold, 6)
    if threshold <= 0:
        noisy_end = clean_start = 0.0
    elif threshold >= 1:
        noisy_end = clean_start = 1.0
    else:
        noisy_end = clean_start = threshold + BOUNDARY_EPSILON

    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    output: list[list[Any]] = []

    for row in conditioning:
        tensor, metadata = row[0], dict(row[1])
        current_batch = tensor.shape[0]
        target_batch = max(current_batch, batch_size)
        processing = tensor
        if current_batch == 1 and target_batch > 1:
            processing = tensor.repeat(target_batch, 1, 1)

        noise = torch.randn(
            processing.size(), generator=generator, device="cpu",
        ).to(processing.device, dtype=processing.dtype)
        noisy = processing + noise * strength

        noisy_start, noisy_stop = _intersection(metadata, 0.0, noisy_end)
        noisy_metadata = metadata.copy()
        noisy_metadata["start_percent"] = noisy_start
        noisy_metadata["end_percent"] = noisy_stop
        output.append([noisy, noisy_metadata])

        clean_start_value, clean_stop = _intersection(metadata, clean_start, 1.0)
        clean_metadata = metadata.copy()
        clean_metadata["start_percent"] = clean_start_value
        clean_metadata["end_percent"] = clean_stop
        output.append([processing, clean_metadata])

    return output


class ConditioningNoiseInjection(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConditioningNoiseInjection",
            display_name="Conditioning Noise Injection",
            category="advanced/conditioning",
            inputs=[
                io.Conditioning.Input("conditioning"),
                io.Float.Input(
                    "threshold", default=0.2, min=0.0, max=1.0, step=0.01,
                ),
                io.Float.Input(
                    "strength", default=10.0, min=0.0, max=100.0, step=1.0,
                ),
            ],
            outputs=[io.Conditioning.Output()],
            hidden=[io.Hidden.prompt],
        )

    @classmethod
    def fingerprint_inputs(
        cls,
        conditioning: sdk.CondRef,
        threshold: float,
        strength: float,
        prompt: Any = None,
    ) -> str:
        del cls, conditioning
        seed, batch = workflow_parameters(prompt)
        return f"{seed}_{batch}_{threshold}_{strength}"

    @classmethod
    async def execute(
        cls,
        conditioning: sdk.CondRef,
        threshold: float,
        strength: float,
        prompt: Any = None,
    ) -> io.NodeOutput:
        del cls
        if not math.isfinite(float(threshold)) or not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be finite and between zero and one")
        if not math.isfinite(float(strength)) or not 0.0 <= strength <= 100.0:
            raise ValueError("strength must be finite and between zero and 100")

        seed, batch_size = workflow_parameters(prompt)
        value = await conditioning.value()
        if not isinstance(value, list) or len(value) > MAX_CONDITIONING_ROWS:
            raise ValueError("conditioning must be a bounded list")

        projected_elements = 0
        for row in value:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                raise ValueError("conditioning rows must contain tensor and metadata")
            tensor, metadata = row[0], row[1]
            if not isinstance(tensor, torch.Tensor) or tensor.dim() != 3:
                raise ValueError("conditioning tensors must be BxSxD")
            if tensor.shape[0] < 1 or tensor.shape[0] > MAX_BATCH:
                raise ValueError("conditioning batch is out of range")
            if tensor.shape[0] > 1 and batch_size > tensor.shape[0]:
                raise ValueError("cannot expand an already-batched conditioning")
            if not isinstance(metadata, dict) or len(metadata) > MAX_METADATA_ITEMS:
                raise ValueError("conditioning metadata must be a bounded mapping")
            projected_elements += tensor.numel() * (
                batch_size if tensor.shape[0] == 1 else 1
            )
            if projected_elements > MAX_TENSOR_ELEMENTS:
                raise ValueError("conditioning tensors exceed the resource limit")

        result = inject_noise(
            value, float(threshold), float(strength), seed, batch_size,
        )
        return io.NodeOutput(await sdk.CondRef.from_value(result))


NODE_CLASS_MAPPINGS = {
    "ConditioningNoiseInjection": ConditioningNoiseInjection,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ConditioningNoiseInjection": "Conditioning Noise Injection",
}


class ConditioningNoiseInjectionExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> ConditioningNoiseInjectionExtension:
    return ConditioningNoiseInjectionExtension()
