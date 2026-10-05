import logging
import math

import torch

from comfy_api.latest import ComfyExtension, io, sdk

#Released under the terms of the MIT No Attribution License
VERSION = "2.2"

NOISE_INSERT_OPTIONS = [
    "noise on beginning steps", "noise on ending steps",
    "noise on all steps", "disabled",
]
MASK_START_OPTIONS = ["beginning", "end"]
MAX_CONDITIONING_ROWS = 64
MAX_METADATA_ITEMS = 256
MAX_TENSOR_ELEMENTS = 268_435_456


def _conditioning_set_values(conditioning, values):
    output = []
    for tensor, metadata in conditioning:
        copied = dict(metadata)
        copied.update(values)
        output.append([tensor, copied])
    return output


class SeedVarianceEnhancer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SeedVarianceEnhancer",
            category="advanced/conditioning",
            inputs=[
                io.Conditioning.Input("conditioning"),
                io.Float.Input(
                    "randomize_percent", default=50.0, min=1.0, max=100.0,
                    step=1, tooltip=(
                        "The percentage of embedding values to which random "
                        "noise is added.")),
                io.Float.Input(
                    "strength", default=20, min=-0xFFFFFFFF,
                    max=0xFFFFFFFF, step=0.00001,
                    tooltip="The scale of the random noise."),
                io.Combo.Input(
                    "noise_insert", options=NOISE_INSERT_OPTIONS,
                    tooltip=(
                        "On which steps of the generation process the noisy "
                        "text embedding is used.")),
                io.Float.Input(
                    "steps_switchover_percent", default=20.0, min=1.0,
                    max=99.0, step=1, tooltip=(
                        "The percentage of steps processed before switching "
                        "between noisy and original embeddings.")),
                io.Int.Input(
                    "seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF,
                    control_after_generate=True,
                    tooltip=(
                        "Random seed. Add 1 billion to strength to restore "
                        "the v2.1 seed behavior.")),
                io.Combo.Input(
                    "mask_starts_at", options=MASK_START_OPTIONS,
                    tooltip="Which end of the prompt is protected from noise."),
                io.Float.Input(
                    "mask_percent", default=0.0, min=0.0, max=99.0, step=1,
                    tooltip="Percentage of the prompt protected from noise."),
                io.Boolean.Input(
                    "log_to_console", default=False,
                    tooltip=(
                        "Print embedding statistics. You are using version "
                        f"{VERSION}.")),
            ],
            outputs=[io.Conditioning.Output()],
        )

    #prints to console statistics about a tensor
    def log_tensor_statistics(self, tensor):
        if not isinstance(tensor, torch.Tensor):
            logging.warning("SeedVarianceEnhancer received a conditioning with no Tensor")
            return

        # Find null sequences
        first_null, last_nonnull, null_sequences = self.tensor_first_null_sequence(tensor)

        if last_nonnull < tensor.size(1) - 1:
            # Slice tensor up to the last_nonnull layer (inclusive) along sequence dimension
            sliced_tensor = tensor[:, :last_nonnull + 1, :]
            # Calculate statistics
            mean = torch.mean(sliced_tensor).item()
            std = torch.std(sliced_tensor).item()
            min_val = torch.min(sliced_tensor).item()
            max_val = torch.max(sliced_tensor).item()
        else:
            # Calculate statistics
            mean = torch.mean(tensor).item()
            std = torch.std(tensor).item()
            min_val = torch.min(tensor).item()
            max_val = torch.max(tensor).item()

        # Log statistics to console
        logging.info(f"Embedding Tensor Statistics:  (from SeedVarianceEnhancer)")
        if first_null != -1:
            # count null sequences
            number_of_null_seq = 0
            for i in null_sequences:
                if i == 0:
                    number_of_null_seq += 1
            logging.info(f"null sequences:   index of first: {first_null}   Index of last nonnull: {last_nonnull}   total: {number_of_null_seq}")
        logging.info(f"  Dimensions: {', '.join(map(str, tensor.shape))}   Min: {min_val:.6f}   Max: {max_val:.6f}   Mean: {mean:.6f}   Standard Deviation: {std:.6f}   Try strength in range {std/10:.6f} - {std*10:.6f}")


    # searches for sequences within a tensor that contain all null bytes
    def tensor_first_null_sequence(self, tensor):
        first_null = -1  # Index of the first sequence that is all zeros
        last_nonnull = -1 # Index of the last sequence that has nonzero values
        null_sequences = [0] * tensor.size(1)  # Initialize array with 0s

        if tensor.dim() == 3:  # Ensure tensor has 3 dimensions
            for i in range(tensor.size(1)):  # Iterate through each sequence in the second dimension
                sequence = tensor[:, i, ...]  # Extract current sequence
                is_all_zero = torch.all(sequence == 0)  # Check if the sequence is all zeros

                # Update the null_sequences array
                null_sequences[i] = 0 if is_all_zero else 1

                if not is_all_zero:
                    last_nonnull = i

                # Track the first null sequence
                if is_all_zero and first_null == -1:
                    first_null = i

        return (first_null, last_nonnull, null_sequences)


    def _randomize_value(self, conditioning, randomize_percent, strength, noise_insert, steps_switchover_percent, seed, mask_starts_at, mask_percent, log_to_console):
        # Validate and scale input
        steps_switchover_percent = max(1, min(99, steps_switchover_percent)) / 100
        randomize_percent = max(1, min(100, randomize_percent)) / 100
        mask_percent = max(0, min(99, mask_percent)) / 100

        # Check for early return conditions
        if len(conditioning) < 1 or len(conditioning[0]) < 2 or ( len(conditioning) == 2 and len(conditioning[1]) < 2 ):
            if log_to_console:
                logging.warning("SeedVarianceEnhancer received an empty conditioning. Passing it through unchanged.")
            return (conditioning,)
        if strength == 0:
            if log_to_console:
                logging.warning(f"SeedVarianceEnhancer is disabled. Strength is set to zero. Passing conditioning through unchanged.")
                self.log_tensor_statistics(conditioning[0][0])
            return (conditioning,)
        if noise_insert == "disabled":
            if log_to_console:
                logging.warning("SeedVarianceEnhancer is disabled. Passing conditioning through unchanged.")
                self.log_tensor_statistics(conditioning[0][0])
            return (conditioning,)

        if len(conditioning) > 2 and log_to_console:
            logging.warning("SeedVarianceEnhancer will only use the first two embeddings from this conditioning.")

        reset_seed = True # By default, we will use new seed behavior in version 2.2 and up
        if int(strength / 1000000000) == 1: # if the user added 1 billion to strength, we will revert to old seed behavior
            strength -= 1000000000
            reset_seed = False
            if log_to_console:
                logging.info("SeedVarianceEnhancer detected 1 billion added to strength. Subtracting the 1B and reverting to v2.1 seed behavior.")

        # Select the embedding we will work with
        if len(conditioning) == 1:
            t = [ conditioning[0][0], conditioning[0][1].copy() ]
            t_other = [ conditioning[0][0], conditioning[0][1].copy() ]
        elif len(conditioning) >= 2:
            if noise_insert == "noise on beginning steps":
                t = [ conditioning[0][0], conditioning[0][1].copy() ]
                t_other = [ conditioning[1][0], conditioning[1][1].copy() ]
            elif noise_insert == "noise on ending steps":
                t = [ conditioning[1][0], conditioning[1][1].copy() ]
                t_other = [ conditioning[0][0], conditioning[0][1].copy() ]
            else: # Doing "noise on all steps." If upstream SVH nodes only added noise to the end, we will use that embedding
                if conditioning[0][1]["SVH_tag"] != "noisy" and conditioning[1][1]["SVH_tag"] == "noisy":
                    t = [ conditioning[1][0], conditioning[1][1].copy() ]
                    t_other = [ conditioning[1][0], conditioning[1][1].copy() ]
                else:
                    t = [ conditioning[0][0], conditioning[0][1].copy() ]
                    t_other = [ conditioning[0][0], conditioning[0][1].copy() ]


        if isinstance(t[0], torch.Tensor):
            if log_to_console:
                self.log_tensor_statistics(t[0]) # print statistical analysis of tensor to console

            # Upstream resets Torch's process-global RNG twice. A local
            # generator preserves its exact seeded draws without letting one
            # workflow perturb concurrent nodes in this guest process.
            generator = torch.Generator(device=t[0].device)
            generator.manual_seed(seed)
            noise = torch.rand(
                t[0].shape,
                dtype=t[0].dtype,
                layout=t[0].layout,
                device=t[0].device,
                generator=generator,
            ) * 2 * strength - strength
            if reset_seed:
                generator.manual_seed(seed + 1)
            noise_mask = torch.bernoulli(
                torch.ones_like(t[0]) * randomize_percent,
                generator=generator,
            ).bool() # Randomly select a percentage of values.

            #check for null sequences
            first_null, last_nonnull, null_sequences = self.tensor_first_null_sequence(t[0])

            # Check if we need to apply masking logic based on mask_percent or null sequences
            if mask_percent > 0 or last_nonnull < t[0].size(1) - 1:
                if last_nonnull < t[0].size(1) - 1 and last_nonnull >= 0:
                    seq_len = last_nonnull + 1
                else:
                    seq_len = t[0].size(1)

                if mask_starts_at == "end":
                    mask_start = seq_len - int(seq_len * mask_percent)
                    mask_end = t[0].size(1)
                else:
                    mask_start = 0
                    mask_end = int(seq_len * mask_percent)

                # Create the mask
                prompt_mask = torch.arange(t[0].size(1), device=t[0].device).view(1, -1, 1).expand(t[0].size(0), -1, t[0].size(2))
                prompt_mask = (prompt_mask >= mask_start) & (prompt_mask < mask_end)

                if first_null > -1:  # There are some null sequences
                    if log_to_console:
                        logging.info(f"SeedVarianceEnhancer is masking null sequence from noise")

                    # Create null_mask from null_sequences, reshape, and expand
                    null_mask_tensor = ~torch.tensor(null_sequences, device=t[0].device, dtype=torch.bool)
                    null_mask_tensor = null_mask_tensor.view(1, -1, 1).expand(t[0].size(0), -1, t[0].size(2))

                    # Combine with existing mask to include null sequences in the protected region
                    prompt_mask = prompt_mask | null_mask_tensor  # Logical OR: protect both range and nulls

                # Combine with existing mask
                noise_mask = noise_mask & (~prompt_mask)  # Zeros noise_mask within the mask range and nulls

            modified_noise = noise * noise_mask # Only apply noise to the selected values.
            noisy_tensor = t[0] + modified_noise
            noisy_embedding = [ [noisy_tensor, t[1]] ]
            other_embedding = [ t_other ]

            if noise_insert == "noise on beginning steps":
                new_conditioning = _conditioning_set_values(noisy_embedding, {"start_percent": 0.0, "end_percent": steps_switchover_percent, "SVH_tag" : "noisy"})
                new_conditioning += _conditioning_set_values(other_embedding, {"start_percent": steps_switchover_percent, "end_percent": 1.0})
            elif noise_insert == "noise on ending steps":
                new_conditioning = _conditioning_set_values(other_embedding, {"start_percent": 0.0, "end_percent": steps_switchover_percent})
                new_conditioning += _conditioning_set_values(noisy_embedding, {"start_percent": steps_switchover_percent, "end_percent": 1.0, "SVH_tag" : "noisy"})
            else:
                if "start_percent" in noisy_embedding[0][1]:
                    del noisy_embedding[0][1]["start_percent"]
                if "end_percent" in noisy_embedding[0][1]:
                    del noisy_embedding[0][1]["end_percent"]
                return (noisy_embedding,)

            return (new_conditioning,)

        else: # if t[0] was not a Tensor
            if log_to_console:
                logging.warning("SeedVarianceEnhancer received a conditioning with no Tensor. Passing it through untouched.")
            return (conditioning,)

    @classmethod
    async def execute(
        cls, conditioning: sdk.CondRef, randomize_percent: float,
        strength: float, noise_insert: str,
        steps_switchover_percent: float, seed: int,
        mask_starts_at: str, mask_percent: float,
        log_to_console: bool,
    ) -> io.NodeOutput:
        for name, value in (
            ("randomize_percent", randomize_percent),
            ("strength", strength),
            ("steps_switchover_percent", steps_switchover_percent),
            ("mask_percent", mask_percent),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if noise_insert not in NOISE_INSERT_OPTIONS:
            raise ValueError("unknown noise insertion mode")
        if mask_starts_at not in MASK_START_OPTIONS:
            raise ValueError("unknown prompt-mask origin")
        if isinstance(seed, bool) or not 0 <= int(seed) <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("seed is out of range")

        value = await conditioning.value()
        if not isinstance(value, list) or len(value) > MAX_CONDITIONING_ROWS:
            raise ValueError("conditioning must be a bounded list")
        for row in value:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            tensor, metadata = row[0], row[1]
            if isinstance(tensor, torch.Tensor):
                if tensor.dim() != 3 or tensor.numel() > MAX_TENSOR_ELEMENTS:
                    raise ValueError("conditioning tensor must be bounded BxSxD")
            if isinstance(metadata, dict) and len(metadata) > MAX_METADATA_ITEMS:
                raise ValueError("conditioning metadata is too large")

        result = cls()._randomize_value(
            value, randomize_percent, strength, noise_insert,
            steps_switchover_percent, int(seed), mask_starts_at,
            mask_percent, bool(log_to_console))[0]
        return io.NodeOutput(await sdk.CondRef.from_value(result))


NODE_CLASS_MAPPINGS = {
    "SeedVarianceEnhancer": SeedVarianceEnhancer
}


class SeedVarianceEnhancerExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> SeedVarianceEnhancerExtension:
    return SeedVarianceEnhancerExtension()
