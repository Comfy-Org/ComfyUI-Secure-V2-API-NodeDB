"""Authority-free Secure Nodes V2 seed generator."""

import random
import time

from comfy_api.latest import ComfyExtension, io


MIN_SEED = 0
MAX_SEED = 0xFFFFFFFFFFFFFFFF
MODES = ["fixed", "increment", "decrement", "random"]


class AdvancedSeedGenerator(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    _last_seed = 0

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AdvancedSeedGenerator",
            display_name="🎲 Advanced Seed Generator",
            category="utils",
            inputs=[
                io.Combo.Input("mode", options=MODES),
                io.Int.Input(
                    "seed", default=0, min=MIN_SEED, max=MAX_SEED,
                    step=1, display_mode=io.NumberDisplay.number,
                ),
            ],
            outputs=[io.Int.Output("seed")],
        )

    @classmethod
    def execute(cls, mode: str, seed: int) -> io.NodeOutput:
        if mode == "fixed":
            result = seed
        elif mode == "random":
            result = random.randint(MIN_SEED, MAX_SEED)
        elif mode == "increment":
            result = MIN_SEED if cls._last_seed == MAX_SEED else cls._last_seed + 1
        elif mode == "decrement":
            result = MAX_SEED if cls._last_seed == MIN_SEED else cls._last_seed - 1
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

        if mode in ("random", "increment", "decrement"):
            cls._last_seed = result
        return io.NodeOutput(result)

    @classmethod
    def fingerprint_inputs(cls, mode: str, seed: int):
        if mode in ("random", "increment", "decrement"):
            return time.time()
        return f"fixed_{seed}"

    @classmethod
    def reset_state(cls) -> None:
        cls._last_seed = MIN_SEED


NODE_CLASS_MAPPINGS = {"AdvancedSeedGenerator": AdvancedSeedGenerator}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedSeedGenerator": "🎲 Advanced Seed Generator",
}


class RandomSeedGeneratorExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [AdvancedSeedGenerator]


async def comfy_entrypoint() -> ComfyExtension:
    return RandomSeedGeneratorExtension()
