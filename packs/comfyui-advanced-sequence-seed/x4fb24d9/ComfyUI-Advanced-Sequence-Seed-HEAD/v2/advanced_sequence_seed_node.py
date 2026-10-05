"""Secure Nodes V2 implementation of Advanced Sequence Seed Generator."""

from __future__ import annotations

import math
import random

from comfy_api.latest import io


SEQUENCE_TYPES = (
    "Fibonacci", "Prime", "Padovan", "Triangular", "Catalan", "Pell", "Lucas",
)


class AdvancedSequenceSeedNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AdvancedSequenceSeedNode",
            display_name="Advanced Sequence Seed Generator",
            category="AI WizArt",
            is_output_node=True,
            inputs=[
                io.Combo.Input("sequence_type", options=list(SEQUENCE_TYPES), default="Fibonacci"),
                io.Int.Input("max_sequence_length", default=20, min=2, max=1000),
                io.Int.Input("seed_range_start", default=0, min=0, max=999),
                io.Int.Input("seed_range_end", default=19, min=1, max=1000),
                io.Boolean.Input("force_recalculation", default=True),
                io.Int.Input("current_seed", default=0, min=0, max=9_999_999_999, step=1),
                io.Float.Input(
                    "noise_factor", default=0.0, min=0.0, max=1.0,
                    step=0.01, optional=True,
                ),
            ],
            outputs=[io.Int.Output("INT", display_name="INT")],
        )

    @staticmethod
    def is_prime(value: int) -> bool:
        if value < 2:
            return False
        for candidate in range(2, math.isqrt(value) + 1):
            if value % candidate == 0:
                return False
        return True

    @classmethod
    def generate_primes(cls, length: int) -> list[int]:
        primes: list[int] = []
        candidate = 2
        while len(primes) < length:
            if cls.is_prime(candidate):
                primes.append(candidate)
            candidate += 1
        return primes

    @classmethod
    def generate_sequence(cls, sequence_type: str, length: int) -> list[int]:
        if sequence_type == "Fibonacci":
            sequence = [0, 1]
            while len(sequence) < length:
                sequence.append(sequence[-1] + sequence[-2])
        elif sequence_type == "Prime":
            sequence = cls.generate_primes(length)
        elif sequence_type == "Padovan":
            sequence = [1, 1, 1]
            while len(sequence) < length:
                sequence.append(sequence[-2] + sequence[-3])
        elif sequence_type == "Triangular":
            sequence = [number * (number + 1) // 2 for number in range(1, length + 1)]
        elif sequence_type == "Catalan":
            sequence = [1]
            for number in range(1, length):
                sequence.append(sequence[-1] * 2 * (2 * number - 1) // (number + 1))
        elif sequence_type == "Pell":
            sequence = [0, 1]
            while len(sequence) < length:
                sequence.append(2 * sequence[-1] + sequence[-2])
        elif sequence_type == "Lucas":
            sequence = [2, 1]
            while len(sequence) < length:
                sequence.append(sequence[-1] + sequence[-2])
        else:
            raise ValueError(f"Unsupported sequence type: {sequence_type}")
        # Preserve the upstream Padovan edge case: its three base values are
        # returned even when the requested (schema-minimum) length is two.
        return sequence

    @classmethod
    def execute(
        cls,
        sequence_type: str,
        max_sequence_length: int,
        seed_range_start: int,
        seed_range_end: int,
        force_recalculation: bool,
        current_seed: int,
        noise_factor: float = 0.0,
    ) -> io.NodeOutput:
        if force_recalculation or current_seed == 0:
            sequence = cls.generate_sequence(sequence_type, max_sequence_length)
            valid_range = sequence[seed_range_start:min(seed_range_end + 1, len(sequence))]
            if not valid_range:
                raise ValueError("Invalid range specified for the sequence")
            seed = valid_range[random.randint(0, len(valid_range) - 1)]
        else:
            seed = current_seed

        if noise_factor > 0:
            noise = random.uniform(-noise_factor, noise_factor) * seed
            seed = int(seed + noise)

        return io.NodeOutput(seed, ui={"seed": [seed]})

    @classmethod
    def fingerprint_inputs(
        cls, force_recalculation: bool, current_seed: int, **_kwargs: object,
    ) -> float | str:
        if force_recalculation or current_seed == 0:
            return float("nan")
        return ""


NODE_CLASS_MAPPINGS = {"AdvancedSequenceSeedNode": AdvancedSequenceSeedNode}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedSequenceSeedNode": "Advanced Sequence Seed Generator",
}
