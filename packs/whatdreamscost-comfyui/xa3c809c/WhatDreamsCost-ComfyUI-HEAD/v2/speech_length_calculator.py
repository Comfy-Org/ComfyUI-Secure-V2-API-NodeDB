"""Secure V2 implementation of Speech Length Calculator."""
from __future__ import annotations

import math
import re

from comfy_api.latest import io


class SpeechLengthCalculator(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SpeechLengthCalculator",
            display_name="Speech Length Calculator",
            category="WhatDreamsCost",
            inputs=[
                io.String.Input(
                    "text",
                    multiline=True,
                    default='Enter your script here. "Make sure to put spoken words inside quotes!"',
                ),
                io.Int.Input("fps", default=24, min=1, max=120, step=1),
                io.Float.Input("additional_time", default=0.0, min=0.0, step=0.1),
                io.String.Input("text_input", optional=True, force_input=True),
            ],
            outputs=[
                io.Int.Output("slow_frame_count", display_name="slow_frame_count"),
                io.Int.Output("average_frame_count", display_name="average_frame_count"),
                io.Int.Output("fast_frame_count", display_name="fast_frame_count"),
                io.String.Output("text", display_name="text"),
            ],
        )

    @classmethod
    def execute(
        cls,
        text: str,
        fps: int,
        additional_time: float = 0.0,
        text_input: str | None = None,
    ) -> io.NodeOutput:
        active_text = (
            text_input
            if isinstance(text_input, str) and text_input.strip()
            else text
        )
        matches = re.findall(
            r'"([^"]*)"|\'([^\']*)\'|“([^”]*)”|‘([^’]*)’',
            active_text,
        )
        quoted_text = " ".join(next((group for group in match if group), "") for match in matches)
        word_count = len(quoted_text.split())

        def frames(words_per_minute: int) -> int:
            if word_count == 0 and additional_time == 0:
                return 0
            seconds = word_count / words_per_minute * 60 + additional_time
            return math.ceil(seconds * fps)

        slow, average, fast = frames(100), frames(130), frames(160)
        return io.NodeOutput(
            slow,
            average,
            fast,
            active_text,
            ui={"speech_length": [{
                "text": active_text,
                "fps": fps,
                "additional_time": additional_time,
                "word_count": word_count,
                "slow": slow,
                "average": average,
                "fast": fast,
            }]},
        )


NODE_CLASS_MAPPINGS = {"SpeechLengthCalculator": SpeechLengthCalculator}
