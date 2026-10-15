"""Actual-ID successor for full-library consumers; not whole-pack registration."""
from comfy_api.latest import io

from .secure_text_nodes import Text as SnapshotText, Prompt as SnapshotPrompt
from .secure_services.full_wildcards import expand_saved_text, encode_saved_prompt


class Text(SnapshotText):
    @classmethod
    async def execute(cls, text, seed=None, prompt=None, unique_id=None):
        return io.NodeOutput(await expand_saved_text(text, seed))


class Prompt(SnapshotPrompt):
    @classmethod
    async def execute(cls, text, clip, seed=None, prompt=None, unique_id=None, **kwargs):
        return io.NodeOutput(*await encode_saved_prompt(clip, text, seed, **kwargs))
