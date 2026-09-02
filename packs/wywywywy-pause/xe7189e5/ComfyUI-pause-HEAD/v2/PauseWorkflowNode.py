"""Secure Nodes V2 implementation of the pinned workflow pause nodes."""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk


_INTERACTION_KIND = "prompt-await"
_INTERACTION_VARIANT = "wywywywy-workflow-pause-v1"
_INTERACTION_TIMEOUT = 540.0


class _PauseWorkflowBase(io.ComfyNode):
    """Await one prompt-scoped decision, then pass inputs through unchanged."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("ui.interact", "execution.interrupt")
    PLAY_SOUND = False
    NODE_ID = ""
    DISPLAY_NAME = ""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=cls.NODE_ID,
            display_name=cls.DISPLAY_NAME,
            category="utils",
            inputs=[
                io.AnyType.Input("any1"),
                io.AnyType.Input("any2", optional=True),
            ],
            outputs=[
                io.AnyType.Output("any1", display_name="any1"),
                io.AnyType.Output("any2", display_name="any2"),
            ],
            hidden=[io.Hidden.unique_id],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls, any1: Any = None, any2: Any = None,
    ) -> io.NodeOutput:
        payload = {
            "variant": _INTERACTION_VARIANT,
            "sound": cls.PLAY_SOUND,
            "title": cls.DISPLAY_NAME,
        }
        try:
            response = await sdk.ctx().interact.request(
                _INTERACTION_KIND,
                payload,
                timeout=_INTERACTION_TIMEOUT,
            )
        except Exception as error:
            remote_type = str(
                getattr(error, "remote_type", type(error).__name__)
            )
            if (
                remote_type in {"TimeoutError", "CancelledError"}
                and "timeout" in str(error).lower()
            ):
                await cls._interrupt("Pause Workflow timed out")
            raise

        if not isinstance(response, dict):
            raise TypeError("pause response must be an object")
        action = response.get("action")
        if action == "continue":
            return io.NodeOutput(any1, any2)
        if action == "cancel":
            await cls._interrupt("Pause Workflow was cancelled")
        raise ValueError("pause response action must be 'continue' or 'cancel'")

    @staticmethod
    async def _interrupt(reason: str) -> None:
        await sdk.ctx().execution.interrupt()
        raise RuntimeError(reason)


class PauseWorkflowNode(_PauseWorkflowBase):
    NODE_ID = "PauseWorkflowNode"
    DISPLAY_NAME = "Pause Workflow"


class PauseWorkflowNodeWithSound(_PauseWorkflowBase):
    NODE_ID = "PauseWorkflowNodeWithSound"
    DISPLAY_NAME = "Pause Workflow (Sound)"
    PLAY_SOUND = True


__all__ = ["PauseWorkflowNode", "PauseWorkflowNodeWithSound"]
