"""Secure Nodes V2 implementation of Simple Prompt Batcher."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io


MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_PROMPTS = 4096
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


def _bounded_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError(f"{name} is too large")
    return value


def batch_prompts(prepend: str = "", prompts: str = "", append: str = "") -> list[str]:
    """Preserve the pinned pack's exact filtering and separator behavior."""
    prepend = _bounded_text(prepend, "prepend")
    prompts = _bounded_text(prompts, "prompts")
    append = _bounded_text(append, "append")
    prompt_list = [line.strip() for line in prompts.split("\n") if line.strip()]
    if not prompt_list:
        print("[Prompt Batcher] ⚠️ No prompts provided, returning empty prompt")
        return [""]
    if len(prompt_list) > MAX_PROMPTS:
        raise ValueError(f"prompts contains more than {MAX_PROMPTS} non-empty lines")
    prompt_list = [
        f"{prepend}{', ' if prepend else ''}{prompt}{', ' if append else ''}{append}"
        for prompt in prompt_list
    ]
    if sum(len(prompt.encode("utf-8")) for prompt in prompt_list) > MAX_OUTPUT_BYTES:
        raise ValueError("batched prompt output is too large")
    print(f"[Prompt Batcher] 📋 Batching {len(prompt_list)} prompts:")
    for index, prompt in enumerate(prompt_list, 1):
        preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
        print(f"[Prompt Batcher]   {index}. {preview}")
    return prompt_list


class SimplePromptBatcher(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SimplePromptBatcher",
            display_name="📝 Simple Prompt Batcher",
            category="utils/text",
            description=(
                "Simple prompt batcher - one prompt per line\n"
                "Automatically batches through all prompts for inference\n"
                "Allows a global style to be appended to all prompts"
            ),
            inputs=[
                io.String.Input(
                    "prepend", default="", multiline=True,
                    placeholder="Text to prepend to all prompts",
                    tooltip="Text prepended to every prompt.",
                ),
                io.String.Input(
                    "prompts", default="", multiline=True,
                    placeholder=(
                        "Prompts (one per line). Enter one prompt per line. "
                        "No empty lines between prompts."
                    ),
                    tooltip=(
                        "Each line is treated as a separate prompt for batch processing."
                    ),
                ),
                io.String.Input(
                    "append", default="", multiline=True,
                    placeholder="Text to append to all prompts",
                    tooltip="Text appended to every prompt.",
                ),
            ],
            outputs=[
                io.String.Output(
                    "prompt", display_name="prompt", is_output_list=True,
                ),
            ],
        )

    @classmethod
    def execute(
        cls, prepend: str = "", prompts: str = "", append: str = "",
    ) -> io.NodeOutput:
        return io.NodeOutput(batch_prompts(prepend, prompts, append))


NODE_CLASS_MAPPINGS = {"SimplePromptBatcher": SimplePromptBatcher}


class SimplePromptBatcherExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SimplePromptBatcher]


async def comfy_entrypoint() -> SimplePromptBatcherExtension:
    return SimplePromptBatcherExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "SimplePromptBatcher",
    "SimplePromptBatcherExtension",
    "batch_prompts",
    "comfy_entrypoint",
]
